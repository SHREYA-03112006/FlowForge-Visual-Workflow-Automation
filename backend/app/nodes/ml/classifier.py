import asyncio

from ..base import BaseNode, NodeError, NodeResult, NodeRun, field_spec, load_integration
from ..registry import register


@register
class MLClassifierNode(BaseNode):
    type = "ml_classifier"
    category = "ml"
    label = "ML Text Classifier"
    description = "Classifies text with the model trained in ml_model_train/. Output: {label, confidence}."
    fields = [field_spec("text", "Text", "textarea", required=True, placeholder="{{trigger.text}}")]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        predict_mod = load_integration("ml_model_train.predict")
        try:
            res = await asyncio.to_thread(predict_mod.predict, str(config["text"]))
        except FileNotFoundError:
            raise NodeError("Model not trained yet. Run: python -m ml_model_train.train") from None
        if not isinstance(res, dict) or "label" not in res:
            raise NodeError("predict() must return a dict containing at least 'label'")
        output = dict(res)
        output["confidence"] = round(float(output.get("confidence", 0.0)), 4)
        return NodeResult(output=output, message=f"Predicted '{output['label']}' ({output['confidence']:.0%})")
