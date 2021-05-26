from types import ModuleType
from typing import Any, Dict, List, Optional, Type, Union

import fastapi

from modelkit.core.library import ModelConfiguration, ModelLibrary, ServiceSettings
from modelkit.log import logger

# create APIRoute for model
# create startup event


class ModelkitAPIRouter(fastapi.APIRouter):
    def __init__(
        self,
        # PredictionService arguments
        settings: Optional[Union[Dict, ServiceSettings]] = None,
        assetsmanager_settings: Optional[dict] = None,
        configuration: Optional[
            Dict[str, Union[Dict[str, Any], ModelConfiguration]]
        ] = None,
        models: Optional[Union[ModuleType, Type, List]] = None,
        required_models: Optional[Union[List[str], Dict[str, Any]]] = None,
        # APIRouter arguments
        **kwargs,
    ) -> None:
        # add custom startup/shutdown events
        on_startup = kwargs.pop("on_startup", [])
        # on_startup.append(self._on_startup)
        kwargs["on_startup"] = on_startup
        on_shutdown = kwargs.pop("on_shutdown", [])
        on_shutdown.append(self._on_shutdown)
        kwargs["on_shutdown"] = on_shutdown
        super().__init__(**kwargs)

        self.svc = ModelLibrary(
            required_models=required_models,
            settings=settings,
            assetsmanager_settings=assetsmanager_settings,
            configuration=configuration,
            models=models,
        )

    async def _on_shutdown(self):
        await self.svc.close_connections()


class ModelkitAutoAPIRouter(ModelkitAPIRouter):
    def __init__(
        self,
        # PredictionService arguments
        required_models: Optional[List[str]] = None,
        settings: Optional[Union[Dict, ServiceSettings]] = None,
        assetsmanager_settings: Optional[dict] = None,
        configuration: Optional[
            Dict[str, Union[Dict[str, Any], ModelConfiguration]]
        ] = None,
        models: Optional[Union[ModuleType, Type, List]] = None,
        # paths overrides change the configuration key into a path
        route_paths: Optional[Dict[str, str]] = None,
        # APIRouter arguments
        **kwargs,
    ) -> None:
        super().__init__(
            required_models=required_models,
            settings=settings,
            assetsmanager_settings=assetsmanager_settings,
            configuration=configuration,
            models=models,
            **kwargs,
        )

        route_paths = route_paths or {}
        for model_name in self.svc.required_models:
            m = self.svc.get(model_name)
            path = route_paths.get(model_name, "/predict/" + model_name)

            summary = ""
            description = ""
            if m.__doc__:
                doclines = m.__doc__.strip().split("\n")
                summary = doclines[0]
                if len(doclines) > 1:
                    description = "".join(doclines[1:])

            self.add_api_route(
                path,
                self._make_model_endpoint_fn(model_name, m._item_type),
                methods=["POST"],
                description=description,
                summary=summary,
            )
            logger.info("Added model to service", name=model_name, path=path)

    def _make_model_endpoint_fn(self, model_name, item_type):
        def _endpoint(
            item: item_type = fastapi.Body(...),
            model=fastapi.Depends(lambda: self.svc.get(model_name)),
        ):  # noqa: B008
            return model.predict(item)

        return _endpoint
