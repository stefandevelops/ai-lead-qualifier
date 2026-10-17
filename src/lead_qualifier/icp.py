from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_ICP_PATH = Path(__file__).resolve().parents[2] / "data" / "icp.yaml"


@dataclass(frozen=True)
class Seller:
    name: str
    product: str
    sender_name: str
    sender_title: str
    sender_email: str


@dataclass(frozen=True)
class ICP:
    seller: Seller
    hot_threshold: int
    warm_threshold: int
    weights: dict[str, int]
    seniority: dict[str, list[str]]
    company_size: dict[str, int]
    industries: dict[str, list[str]]
    geography: dict[str, list[str]]
    intent: dict[str, list[str]]

    def weight(self, name: str) -> int:
        return int(self.weights.get(name, 0))


def load_icp(path: Path | None = None) -> ICP:
    source = Path(path) if path else DEFAULT_ICP_PATH
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    return icp_from_dict(raw)


def icp_from_dict(raw: dict) -> ICP:
    seller = raw.get("seller") or {}
    tiers = raw.get("tiers") or {}
    return ICP(
        seller=Seller(
            name=seller.get("name", "Northstar CS"),
            product=seller.get("product", "customer operations platform"),
            sender_name=seller.get("sender_name", "Alex Rivera"),
            sender_title=seller.get("sender_title", "Account Executive"),
            sender_email=seller.get("sender_email", "alex@northstar-cs.example"),
        ),
        hot_threshold=int(tiers.get("hot", 75)),
        warm_threshold=int(tiers.get("warm", 50)),
        weights=dict(raw.get("weights") or {}),
        seniority={k: [str(x).lower() for x in v] for k, v in (raw.get("seniority") or {}).items()},
        company_size={k: int(v) for k, v in (raw.get("company_size") or {}).items()},
        industries={k: list(v) for k, v in (raw.get("industries") or {}).items()},
        geography={k: [str(x).upper() for x in v] for k, v in (raw.get("geography") or {}).items()},
        intent={k: [str(x).lower() for x in v] for k, v in (raw.get("intent") or {}).items()},
    )


def dump_icp(icp: ICP) -> dict:
    return {
        "seller": {
            "name": icp.seller.name,
            "product": icp.seller.product,
            "sender_name": icp.seller.sender_name,
            "sender_title": icp.seller.sender_title,
            "sender_email": icp.seller.sender_email,
        },
        "tiers": {"hot": icp.hot_threshold, "warm": icp.warm_threshold},
        "weights": icp.weights,
        "seniority": icp.seniority,
        "company_size": icp.company_size,
        "industries": icp.industries,
        "geography": icp.geography,
        "intent": icp.intent,
    }
