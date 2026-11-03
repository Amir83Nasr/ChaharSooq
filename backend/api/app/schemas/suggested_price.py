"""Suggested price formula boundary schemas."""

import ast
import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TopGroup = Literal["فرش", "مبلمان", "لوازم خانگی"]


class SuggestedPriceFormulaIn(BaseModel):
    top_group: TopGroup
    expression: str = Field(min_length=1, max_length=256)

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        try:
            root = ast.parse(value, mode="eval")
        except SyntaxError as error:
            raise ValueError("فرمول معتبر نیست") from error

        allowed_nodes = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Pow,
            ast.Mod,
            ast.UAdd,
            ast.USub,
            ast.Constant,
            ast.Name,
            ast.Load,
        )
        nodes = ast.walk(root)
        if any(not isinstance(node, allowed_nodes) for node in nodes):
            raise ValueError("فرمول فقط می‌تواند شامل عدد، x و عملگرهای ریاضی باشد")
        nodes = list(ast.walk(root))
        if any(
            isinstance(node, ast.Constant)
            and (
                isinstance(node.value, bool)
                or not isinstance(node.value, (int, float))
                or (isinstance(node.value, float) and not math.isfinite(node.value))
            )
            for node in nodes
        ):
            raise ValueError("مقادیر ثابت فرمول باید عدد باشند")
        if any(isinstance(node, ast.Name) and node.id != "x" for node in nodes):
            raise ValueError("تنها متغیر مجاز در فرمول x است")
        if not any(isinstance(node, ast.Name) and node.id == "x" for node in nodes):
            raise ValueError("فرمول باید شامل متغیر x باشد")
        return value.strip()


class SuggestedPriceFormulaOut(SuggestedPriceFormulaIn):
    pass
