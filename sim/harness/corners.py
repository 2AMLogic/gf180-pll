"""Process / voltage / temperature corner definitions for gf180mcu.

gf180mcu has no single global corner switch: each device family carries its
own ``.lib`` section in ``sm141064.ngspice``. This repo's device menu (see
``sim/README.md``) uses four families:

    MOS       typical | ff | ss | fs | sf
    resistor  res_typical | res_ff | res_ss
    MOS cap   moscap_typical | moscap_ff | moscap_ss
    MIM cap   mimcap_typical | mimcap_ff | mimcap_ss

(No BJT/diode axis: unlike the sister ``gf180-bandgap`` repo, no block in
this repo uses those device families.)

A *named corner* here is therefore a bundle of sections, one per family,
always in the order (MOS, resistor, MOS cap, MIM cap). ``design.ngspice`` is
always included ahead of them because it defines the global switch params
(``sw_stat_global``, ``sw_stat_mismatch``, ...) the sections reference.

Per ``sim/README.md``'s "Default corner matrix": the five MOS bundles
(``typical``/``ff``/``ss``/``fs``/``sf``) are MOS-only -- passives stay at
``*_typical`` -- because "a MOS-corner-only sweep silently leaves every
passive at typical" is a *documented, allowed* choice for claims that don't
depend on the passives, not a bug. Passive-only bundles (``res_ff``,
``mimcap_ss``, ...) and the combined ``all-slow`` / ``all-fast`` bundles
exist for claims that do depend on them (e.g. the loop filter).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

#: Symbolic names a grid block may use instead of a numeric supply, so a
#: thinning rule survives a ``--supply`` / ``--supply-tol`` override.
SUPPLY_ALIASES = ("low", "nom", "high")

# Default PVT axes. CLAUDE.md and sim/README.md mandate these on every
# recorded result unless the record states why a subset was used.
DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)
DEFAULT_SUPPLY_TOLERANCE: float = 0.10  # +/-10 %
DEFAULT_NOMINAL_SUPPLY_V: float = 3.3   # gf180mcu 3.3 V flavor

#: The five canonical MOS process bundles this repo's "full matrix" requires.
REQUIRED_MOS_CORNERS: frozenset[str] = frozenset({"typical", "ff", "ss", "fs", "sf"})


def _bundle(mos: str, res: str, moscap: str, mimcap: str) -> tuple[str, ...]:
    return (mos, res, moscap, mimcap)


@dataclass(frozen=True)
class Corner:
    """A named process corner: an ordered list of model ``.lib`` sections."""

    name: str
    sections: tuple[str, ...]
    description: str = ""


_TYPICAL = _bundle(mos="typical", res="res_typical", moscap="moscap_typical", mimcap="mimcap_typical")


def _mos_only(name: str, mos_section: str, description: str) -> Corner:
    """MOS skewed, passives at typical -- the ``sim/README.md`` default."""
    sections = (mos_section,) + _TYPICAL[1:]
    return Corner(name=name, sections=sections, description=description)


def _passive_only(name: str, family_index: int, section: str, description: str) -> Corner:
    """One passive family skewed, MOS and the other two passives at typical."""
    sections = list(_TYPICAL)
    sections[family_index] = section
    return Corner(name=name, sections=tuple(sections), description=description)


def _all(skew: str, description: str) -> Corner:
    """Every device family skewed the same direction -- a worst/best-case combo."""
    return Corner(
        name=f"all-{'slow' if skew == 'ss' else 'fast'}",
        sections=_bundle(
            mos=skew,
            res=f"res_{skew}",
            moscap=f"moscap_{skew}",
            mimcap=f"mimcap_{skew}",
        ),
        description=description,
    )


CORNERS: dict[str, Corner] = {
    "typical": Corner("typical", _TYPICAL, "all device families typical"),
    "ff": _mos_only("ff", "ff", "MOS fast, passives typical"),
    "ss": _mos_only("ss", "ss", "MOS slow, passives typical"),
    "fs": _mos_only("fs", "fs", "fast NMOS / slow PMOS, passives typical"),
    "sf": _mos_only("sf", "sf", "slow NMOS / fast PMOS, passives typical"),
    # Passive-dominated corners: independent of the MOS skew, per
    # sim/README.md's "Default corner matrix" hazard note.
    "res_ff": _passive_only("res_ff", 1, "res_ff", "resistors fast (low rho), rest typical"),
    "res_ss": _passive_only("res_ss", 1, "res_ss", "resistors slow (high rho), rest typical"),
    "moscap_ff": _passive_only("moscap_ff", 2, "moscap_ff", "MOS caps fast, rest typical"),
    "moscap_ss": _passive_only("moscap_ss", 2, "moscap_ss", "MOS caps slow, rest typical"),
    "mimcap_ff": _passive_only("mimcap_ff", 3, "mimcap_ff", "MIM caps fast, rest typical"),
    "mimcap_ss": _passive_only("mimcap_ss", 3, "mimcap_ss", "MIM caps slow, rest typical"),
    # Combined worst/best case -- named per sim/README.md's own example bundle
    # name ("all-slow"), for claims that want every axis skewed together
    # rather than one at a time (e.g. loop-dynamics worst-case bandwidth).
    "all-slow": _all("ss", "every device family slow"),
    "all-fast": _all("ff", "every device family fast"),
}

CORNER_SETS: dict[str, tuple[str, ...]] = {
    # Minimum bar for a quick smoke run.
    "typical": ("typical",),
    # The five MOS bundles -- sim/README.md's default process axis.
    "mos": ("typical", "ff", "ss", "fs", "sf"),
    # The six single-family passive bundles.
    "passives": ("res_ff", "res_ss", "moscap_ff", "moscap_ss", "mimcap_ff", "mimcap_ss"),
    # Everything: MOS bundles, passive-only bundles, and the two combined
    # worst/best-case bundles.
    "full": (
        "typical", "ff", "ss", "fs", "sf",
        "res_ff", "res_ss", "moscap_ff", "moscap_ss", "mimcap_ff", "mimcap_ss",
        "all-slow", "all-fast",
    ),
}
DEFAULT_CORNER_SET = "mos"


def resolve_corners(names: list[str] | tuple[str, ...] | None) -> list[Corner]:
    """Turn a list of corner *or* corner-set names into Corner objects."""
    if not names:
        names = [DEFAULT_CORNER_SET]
    resolved: list[Corner] = []
    seen: set[str] = set()
    for name in names:
        expanded = CORNER_SETS.get(name, (name,))
        for corner_name in expanded:
            if corner_name in seen:
                continue
            if corner_name not in CORNERS:
                raise KeyError(
                    f"unknown corner {corner_name!r}; "
                    f"known corners: {', '.join(sorted(CORNERS))}; "
                    f"known sets: {', '.join(sorted(CORNER_SETS))}"
                )
            seen.add(corner_name)
            resolved.append(CORNERS[corner_name])
    return resolved


def supply_points(
    nominal_v: float = DEFAULT_NOMINAL_SUPPLY_V,
    tolerance: float = DEFAULT_SUPPLY_TOLERANCE,
) -> list[float]:
    """Nominal supply and its +/- tolerance rails, low to high."""
    if tolerance <= 0:
        return [round(nominal_v, 6)]
    return [
        round(nominal_v * (1.0 - tolerance), 6),
        round(nominal_v, 6),
        round(nominal_v * (1.0 + tolerance), 6),
    ]


@dataclass(frozen=True)
class SweepPoint:
    """One point on an *extra* sweep axis, beyond process/voltage/temperature.

    ``id`` is the ``<name><value>`` field ``sim/README.md`` appends to a
    corner-id (``f200``, ``n64``, ``e0400``), and ``params`` are the deck
    parameters this point injects -- including any *derived* ones (a stop
    time computed from the rate, a one-hot modulus encoding of N), which is
    exactly what a single fixed ``params`` map cannot express.
    """

    axis: str
    id: str
    params: tuple[tuple[str, str], ...] = ()
    description: str = ""

    @property
    def param_map(self) -> dict[str, str]:
        return dict(self.params)


@dataclass(frozen=True)
class SweepAxis:
    """A named extra axis and its declared points, in manifest order."""

    name: str
    points: tuple[SweepPoint, ...]
    description: str = ""

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.points)

    def select(self, ids: list[str] | tuple[str, ...] | None) -> tuple[SweepPoint, ...]:
        """The declared points named by ``ids`` (all of them when ``ids`` is empty)."""
        if not ids:
            return self.points
        by_id = {p.id: p for p in self.points}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise KeyError(
                f"axis {self.name!r} has no point(s) {unknown}; "
                f"declared points: {', '.join(self.ids)}"
            )
        # Declaration order, not the caller's -- the run order is a property of
        # the manifest so two invocations naming the same points agree.
        return tuple(p for p in self.points if p.id in set(ids))


@dataclass(frozen=True)
class GridBlock:
    """One slice of the PVT x extra-axis space that a run actually covers.

    The campaigns this exists for do **not** run the full cross-product: the
    divider chain sweeps N = 4..64 at two stress corners only, three N over
    the full 45-point grid, and drops most of the N = 64 supply points. A run's
    point set is therefore the *union* of blocks like this one, each carrying
    the ``description`` that justifies it in the record -- rather than a
    rectangular product plus an unexplained hole.

    An empty tuple on any axis means "everything the run resolved for that
    axis", so a block that only thins one axis says only that.
    """

    description: str
    corners: tuple[str, ...] = ()
    temperatures_c: tuple[float, ...] = ()
    supplies: tuple[float | str, ...] = ()
    axes: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def axis_map(self) -> dict[str, tuple[str, ...]]:
        return dict(self.axes)


@dataclass(frozen=True)
class PvtPoint:
    """One point in the PVT grid -- exactly one ngspice invocation."""

    corner: Corner
    temp_c: float
    vdd: float
    index: int = field(default=0, compare=False)
    #: Selected point on each declared extra axis, in axis-declaration order.
    axis_points: tuple[SweepPoint, ...] = ()
    #: Description of the grid block this point was first produced by ("" for
    #: a plain full-factorial run). Excluded from equality: two blocks that
    #: overlap describe the *same* simulation, which is run once.
    block: str = field(default="", compare=False)

    @property
    def corner_id(self) -> str:
        """The ``<process>_<temp>c_<supply>v[_<extra>...]`` id from ``sim/README.md``.

        This is the ratified corner naming for evidence records: the raw log
        for this point is ``corners/<record-id>/<corner-id>.log`` (e.g.
        ``ss_-40c_2.97v.log``, ``typical_27c_3.30v.log``). Supply is always
        written to two decimals per the README's naming convention.

        A campaign that sweeps an independent variable *in addition to* the
        PVT grid appends one further ``_``-separated ``<name><value>`` field
        per extra axis, in axis-declaration order --
        ``ss_125c_2.97v_f200_n64`` -- which is the convention ``sim/README.md``
        already ratifies under "Campaigns that sweep beyond the PVT grid".
        """
        base = f"{self.corner.name}_{self.temp_c:g}c_{self.vdd:.2f}v"
        return base + "".join(f"_{sp.id}" for sp in self.axis_points)

    @property
    def axes(self) -> dict[str, str]:
        """``{axis-name: point-id}`` for this point's extra axes."""
        return {sp.axis: sp.id for sp in self.axis_points}

    @property
    def params(self) -> dict[str, str]:
        """Deck parameters contributed by this point's extra axes.

        Later axes win on a key collision, which is what lets a fine-grained
        axis (N) override a coarse one's default (the timestep chosen per
        rate) rather than forcing every axis to name a disjoint parameter set.
        """
        out: dict[str, str] = {}
        for sp in self.axis_points:
            out.update(sp.param_map)
        return out

    def as_dict(self) -> dict:
        record = {
            "corner": self.corner.name,
            "corner_sections": list(self.corner.sections),
            "temp_c": self.temp_c,
            "vdd": self.vdd,
            "corner_id": self.corner_id,
        }
        if self.axis_points:
            record["axes"] = self.axes
            record["axis_params"] = self.params
        if self.block:
            record["grid_block"] = self.block
        return record


def build_grid(
    corners: list[Corner],
    temperatures: list[float] | tuple[float, ...],
    supplies: list[float],
) -> list[PvtPoint]:
    """Full factorial P x V x T grid, in a stable, reproducible order."""
    points = [
        PvtPoint(corner=corner, temp_c=float(temp), vdd=float(vdd), index=i)
        for i, (corner, temp, vdd) in enumerate(
            itertools.product(corners, temperatures, supplies)
        )
    ]
    return points


def resolve_block_supplies(
    spec: tuple[float | str, ...], supplies: list[float]
) -> list[float]:
    """A grid block's supply restriction, resolved against the run's supplies.

    Entries are either numeric (matched to a resolved supply within 1e-6, so a
    manifest may spell the rail it means) or one of ``low`` / ``nom`` /
    ``high``, which track the *ends* of whatever supply list the run resolved
    and therefore survive a ``--supply`` / ``--supply-tol`` override. A numeric
    entry that matches nothing contributes nothing rather than silently
    widening the block.
    """
    if not spec:
        return list(supplies)
    ordered = sorted(supplies)
    aliases = {
        "low": ordered[0],
        "nom": ordered[len(ordered) // 2],
        "high": ordered[-1],
    }
    chosen: list[float] = []
    for entry in spec:
        if isinstance(entry, str):
            if entry not in aliases:
                raise KeyError(
                    f"unknown supply alias {entry!r}; use a number or one of "
                    + ", ".join(SUPPLY_ALIASES)
                )
            wanted = [aliases[entry]]
        else:
            wanted = [v for v in ordered if abs(v - float(entry)) < 1e-6]
        for value in wanted:
            if value not in chosen:
                chosen.append(value)
    return [v for v in supplies if v in chosen]


def build_sweep_grid(
    corners: list[Corner],
    temperatures: list[float] | tuple[float, ...],
    supplies: list[float],
    axes: list[SweepAxis] | tuple[SweepAxis, ...] = (),
    blocks: list[GridBlock] | tuple[GridBlock, ...] = (),
    axis_filter: dict[str, list[str]] | None = None,
) -> list[PvtPoint]:
    """The point set of a run that sweeps extra axes, possibly non-rectangularly.

    With no ``axes`` this is exactly :func:`build_grid`. With axes and no
    ``blocks`` it is the full cross-product of the PVT grid and every declared
    axis point. With ``blocks`` it is the **union** of those blocks, in block
    order, de-duplicated by corner-id keeping the first occurrence -- so an
    overlapping block re-states coverage without re-simulating it, and the
    point that survives is attributed to the block that first asked for it.

    ``axis_filter`` (``{axis: [point-id, ...]}``, from ``--axis``) narrows the
    declared points of an axis before the blocks are applied, so a debugging
    run can thin an axis without editing the manifest.
    """
    if not axes:
        return build_grid(corners, temperatures, supplies)

    axis_filter = axis_filter or {}
    unknown_axes = sorted(set(axis_filter) - {a.name for a in axes})
    if unknown_axes:
        raise KeyError(
            f"no sweep axis {unknown_axes}; declared axes: "
            + ", ".join(a.name for a in axes)
        )
    available = {a.name: a.select(axis_filter.get(a.name)) for a in axes}

    effective = blocks or (GridBlock(description=""),)
    corner_by_name = {c.name: c for c in corners}
    seen: dict[str, PvtPoint] = {}
    for block in effective:
        block_corners = (
            [corner_by_name[n] for n in block.corners if n in corner_by_name]
            if block.corners
            else list(corners)
        )
        block_temps = (
            [t for t in temperatures if any(abs(t - b) < 1e-6 for b in block.temperatures_c)]
            if block.temperatures_c
            else list(temperatures)
        )
        block_supplies = resolve_block_supplies(block.supplies, supplies)
        wanted = block.axis_map
        try:
            block_axes = [
                [p for p in available[a.name] if not wanted.get(a.name) or p.id in wanted[a.name]]
                for a in axes
            ]
        except KeyError as exc:  # pragma: no cover - guarded by the loader
            raise KeyError(f"grid block {block.description!r}: {exc}") from exc
        for combo in itertools.product(
            block_corners, block_temps, block_supplies, *block_axes
        ):
            corner, temp, vdd = combo[0], combo[1], combo[2]
            point = PvtPoint(
                corner=corner,
                temp_c=float(temp),
                vdd=float(vdd),
                index=len(seen),
                axis_points=tuple(combo[3:]),
                block=block.description,
            )
            seen.setdefault(point.corner_id, point)
    # Re-index so the surviving points number contiguously; de-duplication
    # would otherwise leave gaps wherever two blocks overlapped.
    return [replace(p, index=i) for i, p in enumerate(seen.values())]


def empty_blocks(
    blocks: list[GridBlock] | tuple[GridBlock, ...], points: list[PvtPoint]
) -> list[str]:
    """Declared grid blocks this run produced no point for.

    A block can come up empty when the CLI narrows an axis the block depends
    on (``--corners typical`` against a block scoped to ``ss``/``ff``). That is
    legitimate for a debugging run but must never pass silently, because the
    record would otherwise claim coverage the run does not have.
    """
    covered = {p.block for p in points}
    return [b.description for b in blocks if b.description not in covered]
