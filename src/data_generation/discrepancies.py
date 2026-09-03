from __future__ import annotations
import random
import datetime as dt
from enum import Enum
from typing import Tuple, List

class DiscrepancyProfile(str, Enum):
    EXACT = "EXACT"
    TIMING_LAG = "TIMING_LAG"
    AMOUNT_VARIANCE = "AMOUNT_VARIANCE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    NAME_NOISE = "NAME_NOISE"
    MISSING_RECORD = "MISSING_RECORD"

COUNTERPARTY_CATALOG = [
    {
        "canonical": "Amazon Web Services Inc",
        "category": "Cloud Infrastructure",
        "variations": ["AWS Cloud Services", "AMZN WEB SERVICES", "AWS*US-EAST-1", "AWS Web Services"],
        "base_amount_range": (1000.0, 10000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Google Cloud",
        "category": "Cloud Infrastructure",
        "variations": ["GCP Cloud", "GOOGLE*CLOUD", "Google Cloud Platform", "GCP"],
        "base_amount_range": (500.0, 5000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Microsoft Azure",
        "category": "Cloud Infrastructure",
        "variations": ["MSFT AZURE", "Azure Cloud Services", "MS AZURE COMPUTING", "Microsoft Azure *"],
        "base_amount_range": (800.0, 6000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Stripe",
        "category": "Payment Processing",
        "variations": ["Stripe Inc", "STRIPE*PAYMENTS", "Stripe Checkout", "STRIPE"],
        "base_amount_range": (100.0, 2000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Salesforce",
        "category": "Software",
        "variations": ["Salesforce.com", "SALESFORCE CRM", "SFDC", "Salesforce Inc"],
        "base_amount_range": (2000.0, 8000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Slack",
        "category": "Software",
        "variations": ["Slack Technologies", "SLACK*WORK", "Slack Tech", "SLACKHQ"],
        "base_amount_range": (200.0, 1500.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Atlassian",
        "category": "Software",
        "variations": ["Atlassian Jira", "ATLASSIAN", "Atlassian PTY", "Jira/Confluence"],
        "base_amount_range": (300.0, 2500.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Datadog",
        "category": "Software",
        "variations": ["Datadog Inc", "DATADOG*MONITOR", "Datadog Monitoring", "DATADOG"],
        "base_amount_range": (1000.0, 4000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Snowflake",
        "category": "Software",
        "variations": ["Snowflake Computing", "SNOWFLAKE", "Snowflake Inc", "SNOWFLAKE*DB"],
        "base_amount_range": (1500.0, 7000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Gusto Payroll",
        "category": "HR/Payroll",
        "variations": ["Gusto", "GUSTO*PAYROLL", "Gusto Inc", "GUSTO HR"],
        "base_amount_range": (50.0, 500.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Deel",
        "category": "HR/Payroll",
        "variations": ["Deel Inc", "DEEL*CONTRACTOR", "Deel Global", "DEEL HR"],
        "base_amount_range": (1000.0, 5000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Latham & Watkins",
        "category": "Legal",
        "variations": ["Latham Watkins LLP", "LATHAM & WATKINS", "L&W Legal", "Latham and Watkins"],
        "base_amount_range": (5000.0, 25000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "KPMG",
        "category": "Audit",
        "variations": ["KPMG LLP", "KPMG Audit", "KPMG Advisory", "KPMG"],
        "base_amount_range": (4000.0, 20000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "WeWork",
        "category": "Office",
        "variations": ["WeWork Companies", "WEWORK", "WeWork Office", "WEWORK*RENT"],
        "base_amount_range": (1000.0, 5000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Apple Enterprise",
        "category": "Hardware",
        "variations": ["Apple Inc", "APPLE*B2B", "Apple Store Biz", "APPLE COMP"],
        "base_amount_range": (2000.0, 10000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "SAP",
        "category": "Software",
        "variations": ["SAP SE", "SAP ERP", "SAP*GLOBAL", "SAP Software"],
        "base_amount_range": (3000.0, 15000.0),
        "typical_currency": "EUR"
    },
    {
        "canonical": "British Telecom",
        "category": "Telecommunications",
        "variations": ["BT Group", "BRITISH TELECOM", "BT*COMMUNICATIONS", "British Telecom PLC"],
        "base_amount_range": (100.0, 800.0),
        "typical_currency": "GBP"
    },
    {
        "canonical": "FedEx",
        "category": "Shipping",
        "variations": ["Federal Express", "FEDEX", "FedEx Shipping", "FEDEX*CORP"],
        "base_amount_range": (50.0, 1000.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Silicon Valley Bank",
        "category": "Banking",
        "variations": ["SVB", "SILICON VALLEY BANK", "SVB*FEES", "Silicon Valley Bank Inc"],
        "base_amount_range": (10.0, 200.0),
        "typical_currency": "USD"
    },
    {
        "canonical": "Acme Global Solutions",
        "category": "Consulting",
        "variations": ["Acme Global", "ACME*SOLUTIONS", "Acme Consulting", "Acme Global Inc"],
        "base_amount_range": (1500.0, 5000.0),
        "typical_currency": "USD"
    }
]

class DiscrepancyInjector:
    @staticmethod
    def inject_timing_lag(date: dt.date, rng: random.Random) -> dt.date:
        return date + dt.timedelta(days=rng.randint(1, 4))

    @staticmethod
    def inject_amount_fee(amount: float, rng: random.Random) -> float:
        return round(amount - rng.uniform(15.0, 25.0), 2)

    @staticmethod
    def inject_fx_conversion(amount: float, base_currency: str, rng: random.Random) -> Tuple[float, str]:
        rate = rng.uniform(1.05, 1.25)
        new_currency = "EUR" if base_currency == "USD" else "USD"
        return round(amount * rate, 2), new_currency

    @staticmethod
    def inject_name_variation(canonical: str, variations: List[str], rng: random.Random) -> str:
        return rng.choice(variations)
