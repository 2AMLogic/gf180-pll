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
from dataclasses import dataclass, field

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
class PvtPoint:
    """One point in the PVT grid -- exactly one ngspice invocation."""

    corner: Corner
    temp_c: float
    vdd: float
    index: int = field(default=0, compare=False)

    @property
    def corner_id(self) -> str:
        """The ``<process>_<temp>c_<supply>v`` id from ``sim/README.md``.

        This is the ratified corner naming for evidence records: the raw log
        for this point is ``corners/<record-id>/<corner-id>.log`` (e.g.
        ``ss_-40c_2.97v.log``, ``typical_27c_3.30v.log``). Supply is always
        written to two decimals per the README's naming convention.
        """
        return f"{self.corner.name}_{self.temp_c:g}c_{self.vdd:.2f}v"

    def as_dict(self) -> dict:
        return {
            "corner": self.corner.name,
            "corner_sections": list(self.corner.sections),
            "temp_c": self.temp_c,
            "vdd": self.vdd,
            "corner_id": self.corner_id,
        }


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
