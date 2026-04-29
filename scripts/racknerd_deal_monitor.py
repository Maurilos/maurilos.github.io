#!/usr/bin/env python3
"""
RackNerd annual deal monitor.

Rules implemented by default:
- Only annual USD offers are considered.
- Notify Telegram only when annual price is <= 10.99 USD.
- Ignore 15 USD/year and anything above it.
- Store fingerprints in _data/monitor/racknerd_state.json to avoid duplicate alerts.
- Add more URLs in scripts/monitor_targets.json without changing this script.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: beautifulsoup4. Install with: pip install beautifulsoup4") from exc

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "monitor_targets.json"
STATE_PATH = ROOT / "_data" / "monitor" / "racknerd_state.json"

ANNUAL_WORDS = (
    "annually",
    "annual",
    "yearly",
    "per year",
    "/year",
    "/yr",
    "year",
)

NOISE_LINES = {
    "starting from",
    "order now",
    "added to cart",
    "choose another category",
    "shopping cart",
    "special promos",
    "categories",
    "actions",
    "view cart",
    "register a new domain",
    "transfer in a domain",
    "toggle navigation",
}

FEATURE_HINTS = (
    "vcpu",
    "storage",
    "ram",
    "bandwidth",
    "network",
    "root",
    "ipv4",
    "control panel",
    "available in",
    "gbps",
    "raid",
    "solusvm",
)

TITLE_HINTS = (
    "vps",
    "kvm",
    "hosting",
    "promo",
    "special",
    "ssd",
    "nvme",
    "gb",
)


@dataclass
class Deal:
    target_id: str
    target_name: str
    title: str
    price: float
    currency: str
    billing: str
    url: str
    source_url: str
    context: str
    fingerprint: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_defaults(defaults: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(target)
    return merged


def fetch_url(url: str, user_agent: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - monitored public URL from config
        status = getattr(resp, "status", 200)
        if status < 200 or status >= 400:
            raise RuntimeError(f"HTTP {status}")
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line or "").strip()
    return line


def is_price_line(line: str) -> bool:
    return bool(re.search(r"\$\s*\d+(?:\.\d+)?\s*USD", line, flags=re.I)) or bool(
        re.search(r"\$\s*\d+(?:\.\d+)?\s*/\s*(?:year|yr)", line, flags=re.I)
    )


def looks_like_annual(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in ANNUAL_WORDS)


def extract_price(line: str) -> float | None:
    patterns = [
        r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*USD",
        r"\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*(?:year|yr)",
        r"JUST\s*\$\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*(?:YEAR|YR)",
    ]
    for pattern in patterns:
        match = re.search(pattern, line, flags=re.I)
        if match:
            return float(match.group(1))
    return None


def normalize_for_hash(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def make_fingerprint(target_id: str, title: str, price: float, billing: str, url: str) -> str:
    raw = "|".join(
        [
            target_id,
            normalize_for_hash(title),
            f"{price:.2f}",
            normalize_for_hash(billing),
            normalize_for_hash(url),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def order_links(soup: BeautifulSoup, source_url: str) -> list[str]:
    links: list[str] = []
    for a in soup.find_all("a"):
        text = clean_line(a.get_text(" "))
        if "order now" not in text.lower():
            continue
        href = a.get("href")
        if not href:
            continue
        links.append(urllib.parse.urljoin(source_url, href))
    return links


def find_title(lines: list[str], price_index: int) -> str:
    # Search upwards until a product-like title is found. WHMCS product titles are usually
    # above specs, then price, then Order Now.
    for j in range(price_index - 1, max(-1, price_index - 18), -1):
        candidate = clean_line(lines[j])
        lowered = candidate.lower()
        if not candidate:
            continue
        if lowered in NOISE_LINES:
            continue
        if is_price_line(candidate):
            continue
        if any(hint in lowered for hint in FEATURE_HINTS):
            continue
        if len(candidate) > 120:
            continue
        if any(hint in lowered for hint in TITLE_HINTS):
            return candidate

    # Fallback: use the nearest non-noise line above the price.
    for j in range(price_index - 1, max(-1, price_index - 12), -1):
        candidate = clean_line(lines[j])
        lowered = candidate.lower()
        if candidate and lowered not in NOISE_LINES and not is_price_line(candidate) and len(candidate) <= 120:
            return candidate
    return "Unknown RackNerd offer"


def parse_deals_from_html(target: dict[str, Any], html_text: str) -> list[Deal]:
    soup = BeautifulSoup(html_text, "html.parser")
    source_url = target["url"]
    target_id = target["id"]
    target_name = target.get("name", target_id)
    currency = target.get("currency", "USD")

    lines = [clean_line(x) for x in soup.get_text("\n").splitlines()]
    lines = [x for x in lines if x]
    links = order_links(soup, source_url)

    raw_candidates: list[dict[str, Any]] = []

    for i, line in enumerate(lines):
        price = extract_price(line)
        if price is None:
            continue

        # Some WHMCS pages split "$21.99 USD" and "Annually" into adjacent lines.
        neighborhood = " ".join(lines[max(0, i - 3) : min(len(lines), i + 4)])
        if not looks_like_annual(line) and not looks_like_annual(neighborhood):
            continue

        title = find_title(lines, i)
        context = " | ".join(lines[max(0, i - 4) : min(len(lines), i + 5)])[:500]
        raw_candidates.append(
            {
                "line_index": i,
                "line": line,
                "title": title,
                "price": price,
                "context": context,
                # Prefer canonical WHMCS price rows like "$21.99 USD / Annually"
                # over marketing copy like "JUST $21.99/YEAR".
                "priority": 1 if re.search(r"USD", line, flags=re.I) else 0,
            }
        )

    # WHMCS often shows the same annual price twice for one product:
    # marketing copy, then the canonical "Starting from $X USD Annually" row.
    # Group by title + price, then keep the better canonical candidate.
    grouped: dict[tuple[str, float], dict[str, Any]] = {}
    group_order: list[tuple[str, float]] = []
    for candidate in raw_candidates:
        key = (normalize_for_hash(candidate["title"]), float(candidate["price"]))
        if key not in grouped:
            grouped[key] = candidate
            group_order.append(key)
            continue
        current = grouped[key]
        if (candidate["priority"], candidate["line_index"]) >= (current["priority"], current["line_index"]):
            grouped[key] = candidate

    deals: list[Deal] = []
    for idx, key in enumerate(group_order):
        candidate = grouped[key]
        title = candidate["title"]
        price = float(candidate["price"])
        url = links[idx] if idx < len(links) else source_url
        context = candidate["context"]
        fingerprint = make_fingerprint(target_id, title, price, "annually", url)
        deals.append(
            Deal(
                target_id=target_id,
                target_name=target_name,
                title=title,
                price=price,
                currency=currency,
                billing="annually",
                url=url,
                source_url=source_url,
                context=context,
                fingerprint=fingerprint,
            )
        )

    return deals


def keyword_allowed(deal: Deal, target: dict[str, Any]) -> bool:
    text = f"{deal.title}\n{deal.context}".lower()
    includes = [x.lower() for x in target.get("include_keywords", []) if x]
    excludes = [x.lower() for x in target.get("exclude_keywords", []) if x]
    if includes and not any(k in text for k in includes):
        return False
    if excludes and any(k in text for k in excludes):
        return False
    return True


def is_interesting(deal: Deal, target: dict[str, Any]) -> bool:
    min_price = float(target.get("min_annual_usd", 0.01))
    max_price = float(target.get("max_annual_usd", 10.99))
    ignore_at_or_above = float(target.get("ignore_annual_usd_at_or_above", 15.0))

    if deal.price >= ignore_at_or_above:
        return False
    if not (min_price <= deal.price <= max_price):
        return False
    if not keyword_allowed(deal, target):
        return False
    return True


def telegram_send(text: str) -> None:
    token = os.getenv("TG_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Telegram secrets missing: set TG_BOT_TOKEN and TG_CHAT_ID in GitHub Actions Secrets")

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - Telegram API endpoint
        body = resp.read().decode("utf-8", errors="replace")
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"Telegram HTTP {resp.status}: {body}")
        data = json.loads(body)
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {body}")


def deal_message(deal: Deal) -> str:
    title = html.escape(deal.title)
    target_name = html.escape(deal.target_name)
    price = html.escape(f"${deal.price:.2f} {deal.currency}/year")
    url = html.escape(deal.url, quote=True)
    source_url = html.escape(deal.source_url, quote=True)
    return (
        "🚨 <b>RackNerd 低价年付监控命中</b>\n"
        f"目标：{target_name}\n"
        f"套餐：<b>{title}</b>\n"
        f"价格：<b>{price}</b>\n"
        "规则：只通知约 $10/year，$15/year 及以上忽略\n"
        f"购买链接：<a href=\"{url}\">Order Now</a>\n"
        f"来源页面：<a href=\"{source_url}\">打开页面</a>"
    )


def error_message(target: dict[str, Any], err: Exception) -> str:
    name = html.escape(target.get("name", target.get("id", "unknown")))
    url = html.escape(target.get("url", ""), quote=True)
    err_text = html.escape(str(err))[:500]
    return (
        "⚠️ <b>RackNerd 监控异常</b>\n"
        f"目标：{name}\n"
        f"错误：{err_text}\n"
        f"页面：<a href=\"{url}\">打开检查</a>"
    )


def recovery_message(target: dict[str, Any], deals_count: int) -> str:
    name = html.escape(target.get("name", target.get("id", "unknown")))
    url = html.escape(target.get("url", ""), quote=True)
    return (
        "✅ <b>RackNerd 监控已恢复</b>\n"
        f"目标：{name}\n"
        f"当前可解析年付套餐数量：{deals_count}\n"
        f"页面：<a href=\"{url}\">打开页面</a>"
    )


def state_target(state: dict[str, Any], target_id: str) -> dict[str, Any]:
    targets = state.setdefault("targets", {})
    return targets.setdefault(
        target_id,
        {
            "seen_fingerprints": [],
            "last_error_signature": None,
            "currently_in_error": False,
        },
    )


def signature_for_error(err: Exception) -> str:
    return hashlib.sha256(str(err).encode("utf-8")).hexdigest()[:16]


def main() -> int:
    config = load_json(CONFIG_PATH, {"defaults": {}, "targets": []})
    state = load_json(STATE_PATH, {"version": 1, "targets": {}})
    state_changed = False

    defaults = config.get("defaults", {})
    targets = config.get("targets", [])
    if not targets:
        print("No monitor targets configured.")
        return 0

    total_parsed = 0
    total_interesting = 0
    total_new = 0

    for raw_target in targets:
        target = merge_defaults(defaults, raw_target)
        if not target.get("enabled", True):
            continue

        target_id = target["id"]
        tstate = state_target(state, target_id)
        print(f"Checking {target.get('name', target_id)}: {target['url']}")

        try:
            html_text = fetch_url(target["url"], target.get("user_agent", defaults.get("user_agent", "Mozilla/5.0")))
            deals = parse_deals_from_html(target, html_text)
            interesting = [deal for deal in deals if is_interesting(deal, target)]
            total_parsed += len(deals)
            total_interesting += len(interesting)

            print(f"Parsed annual deals: {len(deals)}; matching <= ${float(target.get('max_annual_usd', 10.99)):.2f}: {len(interesting)}")

            if tstate.get("currently_in_error") and target.get("notify_recovery", True):
                telegram_send(recovery_message(target, len(deals)))
                tstate["currently_in_error"] = False
                tstate["last_error_signature"] = None
                state_changed = True

            seen = set(tstate.get("seen_fingerprints", []))
            for deal in interesting:
                if deal.fingerprint in seen:
                    continue
                telegram_send(deal_message(deal))
                print(f"New matching deal notified: {deal.title} ${deal.price:.2f}/year")
                seen.add(deal.fingerprint)
                total_new += 1
                state_changed = True
                # Tiny pause avoids hitting Telegram too fast if several deals appear.
                time.sleep(1)

            if state_changed:
                tstate["seen_fingerprints"] = sorted(seen)[-200:]
                tstate["last_match_count"] = len(interesting)
                tstate["last_checked_utc"] = utc_now()
                tstate["last_interesting_deals"] = [asdict(deal) for deal in interesting[:20]]

        except Exception as err:  # keep monitor alive and notify once per error signature
            print(f"ERROR while checking {target_id}: {err}", file=sys.stderr)
            if target.get("notify_on_error", True):
                sig = signature_for_error(err)
                if tstate.get("last_error_signature") != sig or not tstate.get("currently_in_error"):
                    telegram_send(error_message(target, err))
                    tstate["last_error_signature"] = sig
                    tstate["currently_in_error"] = True
                    tstate["last_error_utc"] = utc_now()
                    state_changed = True

    state["last_run_utc"] = utc_now()
    state["last_totals"] = {
        "parsed_annual_deals": total_parsed,
        "matching_deals": total_interesting,
        "new_notifications": total_new,
    }

    if state_changed:
        save_json(STATE_PATH, state)
        print(f"State updated: {STATE_PATH}")
    else:
        print("No new matching deals. State unchanged.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
