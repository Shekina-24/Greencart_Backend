from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order, OrderLine, Product, User


def _iso_week(dt) -> str:
    return dt.strftime("%Y-%W")


async def forecast_per_product(
    db: AsyncSession,
    *,
    producer: User,
    window_weeks: int = 8,
    horizon_weeks: int = 4,
) -> List[dict]:
    """Compute a simple moving-average forecast per product (weekly buckets).

    - Aggregate sold quantities per week for each product of the producer.
    - Forecast next `horizon_weeks` as mean of last `window_weeks`.
    """
    stmt: Select = (
        select(
            OrderLine.product_id,
            Product.title,
            Order.created_at,
            func.sum(OrderLine.quantity).label("units"),
        )
        .join(Order, Order.id == OrderLine.order_id)
        .join(Product, Product.id == OrderLine.product_id)
        .where(Product.producer_id == producer.id)
        .group_by(OrderLine.product_id, Product.title, Order.created_at)
        .order_by(Order.created_at)
    )
    rows = (await db.execute(stmt)).all()

    series: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    titles: Dict[int, str] = {}
    for r in rows:
        pid = int(r.product_id)
        titles[pid] = r.title
        bucket = _iso_week(r.created_at)
        series[pid][bucket] += int(r.units or 0)

    results: List[dict] = []
    now = datetime.now(timezone.utc)
    # build future buckets (relative labels only)
    for pid, ts in series.items():
        # take last window_weeks values
        ordered = [units for _, units in sorted(ts.items(), key=lambda kv: kv[0])]
        window = ordered[-window_weeks:] if ordered else []
        avg = sum(window) / len(window) if window else 0.0
        forecast = [int(round(avg)) for _ in range(horizon_weeks)]
        results.append(
            {
                "product_id": pid,
                "title": titles.get(pid, f"#{pid}"),
                "avg_weekly_units": int(round(avg)),
                "forecast_next_weeks": forecast,
            }
        )

    # Include products with no history (avg 0)
    no_history_stmt = select(Product.id, Product.title).where(Product.producer_id == producer.id)
    for pid, title in (await db.execute(no_history_stmt)).all():
        if pid not in series:
            results.append(
                {
                    "product_id": int(pid),
                    "title": title,
                    "avg_weekly_units": 0,
                    "forecast_next_weeks": [0, 0, 0, 0][:horizon_weeks],
                }
            )

    return sorted(results, key=lambda r: (-r["avg_weekly_units"], r["product_id"]))


@dataclass
class _Point:
    x: float
    y: float


def _kmeans(points: List[_Point], k: int, iters: int = 20) -> Tuple[List[_Point], List[int]]:
    if not points:
        return [], []
    # init: pick k evenly spaced points
    centroids = [points[int(i * len(points) / k)] for i in range(k)]
    for _ in range(iters):
        clusters: List[List[_Point]] = [[] for _ in range(k)]
        assign: List[int] = []
        for p in points:
            dists = [((p.x - c.x) ** 2 + (p.y - c.y) ** 2) for c in centroids]
            j = int(min(range(k), key=lambda i: dists[i]))
            clusters[j].append(p)
            assign.append(j)
        new_centroids: List[_Point] = []
        for j in range(k):
            if clusters[j]:
                sx = sum(p.x for p in clusters[j]) / len(clusters[j])
                sy = sum(p.y for p in clusters[j]) / len(clusters[j])
                new_centroids.append(_Point(sx, sy))
            else:
                new_centroids.append(centroids[j])
        centroids = new_centroids
    # final assignment
    final_assign: List[int] = []
    for p in points:
        dists = [((p.x - c.x) ** 2 + (p.y - c.y) ** 2) for c in centroids]
        final_assign.append(int(min(range(k), key=lambda i: dists[i])))
    return centroids, final_assign


async def cluster_consumers(db: AsyncSession, *, k: int = 3) -> dict:
    """Cluster consumers based on average order value and average items per order.
    Returns centroids and segment sizes.
    """
    stmt = (
        select(
            Order.user_id,
            func.count(Order.id).label("orders"),
            func.avg(Order.total_amount_cents).label("aov"),
            func.avg(Order.total_items).label("avg_items"),
        )
        .group_by(Order.user_id)
        .having(func.count(Order.id) > 0)
    )
    rows = (await db.execute(stmt)).all()
    pts: List[_Point] = []
    for r in rows:
        aov = float(r.aov or 0.0)
        avg_items = float(r.avg_items or 0.0)
        # Simple normalization (scale to roughly comparable ranges)
        pts.append(_Point(aov / 10000.0, avg_items / 10.0))
    centroids, assign = _kmeans(pts, k=k)
    counts = [0] * len(centroids)
    for idx in assign:
        if 0 <= idx < len(counts):
            counts[idx] += 1
    return {
        "k": len(centroids),
        "centroids": [{"aov_cents": int(c.x * 10000), "avg_items": round(c.y * 10, 2)} for c in centroids],
        "counts": counts,
    }

