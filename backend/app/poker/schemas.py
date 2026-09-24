"""Схемы, общие для роутеров покера.

`TableRulesSettings` — контракт формы создания стола. Он один и тот же в обе
стороны: форма отправляет эти поля в `POST /rooms`, а `GET /rules/presets`
возвращает готовые значения тех же полей. Держать две похожие модели нельзя —
разъедутся, и заготовка начнёт заполнять форму не тем, что потом отправится.
"""
from pydantic import BaseModel, Field


class TableRulesSettings(BaseModel):
    """Правила стола в виде полей формы.

    Штрафы задаются положительным числом («штраф 5»), знак ставит сервер при
    сборке конфига (`rules.config_from_settings`).
    """

    rounds_start: int = Field(ge=1, description="Сколько карт в первой раздаче")
    rounds_peak: int = Field(ge=1, description="Сколько карт в самой большой раздаче")
    two_beats_ace: bool = Field(description="Двойка бьёт туза своей масти")
    offcolor_beats_oncolor: bool = Field(description="Некозырной джокер бьёт козырного")
    blind_allowed: bool = Field(description="Можно заказать, не открывая руку")
    blind_bonus: int = Field(default=0, ge=0, description="Надбавка за точный заказ вслепую")
    infinite_deck: bool = Field(description="Безлимитная колода: карты повторяются")
    pass_reward: int = Field(ge=0, description="Награда за пас (заказал 0 и взял 0)")
    trick_reward: int = Field(ge=0, description="Награда за каждую взятку при точном заказе")
    overtrick_penalty: int = Field(ge=0, description="Штраф за перебор, положительным числом")
    undertrick_penalty: int = Field(
        ge=0, description="Штраф за каждую недобранную взятку, положительным числом"
    )
