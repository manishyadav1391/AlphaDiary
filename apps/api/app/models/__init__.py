"""Every model is imported here so `Base.metadata` is complete for Alembic."""

from app.models.broker import BrokerAccount, Instrument, OAuthState
from app.models.charges import ChargeRateSet, FillCharge, OrderCharge
from app.models.daily import (
    BenchmarkPrice,
    DailyPlan,
    DailyReview,
    DailySummary,
    MarketHoliday,
)
from app.models.journal import Screenshot, Strategy, Tag, TradeJournal, TradeTag
from app.models.ops import AppSetting, NotificationChannel, NotificationLog, SyncLog
from app.models.raw import Fill, ImportBatch, KiteOrder
from app.models.trade import TradeGroup, TradeGroupFill
from app.models.user import AppSession, AppUser, LoginAttempt

__all__ = [
    "AppSession",
    "AppSetting",
    "AppUser",
    "BenchmarkPrice",
    "BrokerAccount",
    "ChargeRateSet",
    "DailyPlan",
    "DailyReview",
    "DailySummary",
    "Fill",
    "FillCharge",
    "ImportBatch",
    "Instrument",
    "KiteOrder",
    "LoginAttempt",
    "MarketHoliday",
    "NotificationChannel",
    "NotificationLog",
    "OAuthState",
    "OrderCharge",
    "Screenshot",
    "Strategy",
    "SyncLog",
    "Tag",
    "TradeGroup",
    "TradeGroupFill",
    "TradeJournal",
    "TradeTag",
]
