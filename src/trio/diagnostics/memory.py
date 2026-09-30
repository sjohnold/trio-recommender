"""Memory profiles and strict model admission."""

import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum

GIB = 1024**3
MIB = 1024**2

class ProfileName(StrEnum):
    MINI = "Mini"
    BASE = "Base"
    PLUS = "Plus"
    MAX = "Max"

@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    ram_bytes: int
    vram_bytes: int | None = None

    @property
    def capacity_bytes(self) -> int:
        return self.vram_bytes if self.vram_bytes is not None else self.ram_bytes

@dataclass(frozen=True, slots=True)
class Profile:
    name: ProfileName
    budget_bytes: int
    num_ctx: int
    mode_a_billions: tuple[float, float]
    mode_b_billions: tuple[float, float]

PROFILES = (
    Profile(ProfileName.MINI, 6 * GIB, 2048, (1, 1.7), (3, 4)),
    Profile(ProfileName.BASE, 8 * GIB, 4096, (2, 3), (7, 8)),
    Profile(ProfileName.PLUS, 12 * GIB, 8192, (3, 4), (12, 14)),
    Profile(ProfileName.MAX, 24 * GIB, 8192, (7, 8), (27, 32)),
)

def detect_memory() -> MemorySnapshot:
    ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        vram = sum(int(line.strip()) for line in result.stdout.splitlines()) * MIB
        return MemorySnapshot(ram, vram or None)
    except (OSError, subprocess.SubprocessError, ValueError):
        return MemorySnapshot(ram)

def select_profile(snapshot: MemorySnapshot, requested: ProfileName | str | None) -> Profile:
    eligible = [profile for profile in PROFILES if profile.budget_bytes <= snapshot.capacity_bytes]
    if requested is None:
        if not eligible:
            raise ValueError("less than 6 GiB is available")
        return eligible[-1]
    name = ProfileName(requested)
    profile = next(item for item in PROFILES if item.name is name)
    if profile not in eligible:
        raise ValueError(f"{name} exceeds available memory")
    return profile

@dataclass(frozen=True, slots=True)
class ResidentModel:
    name: str
    size: int | None
    size_vram: int | None = None
    is_state: bool = False

class AdmissionReason(StrEnum):
    ADMITTED = "admitted"
    MISSING_STATE_MODEL = "missing_state_model"
    UNKNOWN_SIZE = "unknown_size"
    OVER_BUDGET = "over_budget"

@dataclass(frozen=True, slots=True)
class AdmissionResult:
    admitted: bool
    reason: AdmissionReason
    required_bytes: int
    budget_bytes: int
    reserve_bytes: int

def admit(models: list[ResidentModel], profile: Profile) -> AdmissionResult:
    reserve = max(profile.budget_bytes // 10, 768 * MIB)
    if not any(model.is_state for model in models):
        return AdmissionResult(False, AdmissionReason.MISSING_STATE_MODEL, 0, profile.budget_bytes, reserve)
    sizes = [model.size_vram if model.size_vram is not None else model.size for model in models]
    if any(size is None or size <= 0 for size in sizes):
        return AdmissionResult(False, AdmissionReason.UNKNOWN_SIZE, 0, profile.budget_bytes, reserve)
    required = sum(sizes)  # type: ignore[arg-type]
    admitted = required + reserve <= profile.budget_bytes
    reason = AdmissionReason.ADMITTED if admitted else AdmissionReason.OVER_BUDGET
    return AdmissionResult(admitted, reason, required, profile.budget_bytes, reserve)
