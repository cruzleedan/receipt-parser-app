"""
WORK-0014: the currency a receipt's amounts are in, as an ISO 4217 code.

The model is asked for the code; its answer is cleaned here. Only a known code is kept. Symbols the
model may copy instead are mapped where they are unambiguous (₱ and a lone "P" are pesos on Philippine
receipts); a bare "$" or "¥" names several currencies and gives null, so the app's default is used.
"""

from typing import Optional

# Active ISO 4217 codes.
ISO_4217 = set("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF
CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG
HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA
MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD
RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX
USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL
""".split())

# Unambiguous symbols and local spellings a model may answer with instead of the code.
SYMBOLS = {
    "₱": "PHP", "P": "PHP", "PHP": "PHP", "PESO": "PHP", "PESOS": "PHP", "PHP.": "PHP",
    "US$": "USD", "USD$": "USD", "€": "EUR", "£": "GBP", "₩": "KRW", "₫": "VND", "฿": "THB", "₹": "INR",
    "RP": "IDR", "RM": "MYR", "S$": "SGD", "HK$": "HKD", "NT$": "TWD", "A$": "AUD", "C$": "CAD",
}


def normalise_currency(value: object) -> Optional[str]:
    """The ISO code for the model's answer, or None when it is missing, unknown or ambiguous."""
    if not isinstance(value, str):
        return None
    text = value.strip().upper().replace(" ", "")
    if not text:
        return None
    if text in SYMBOLS:
        return SYMBOLS[text]
    if text in ISO_4217:
        return text
    return None
