"""The cases: one planted bug each, in a real repository or a fixture, and the command an agent would run.

`raw` is the command as an agent types it; what rtk runs instead comes from `rtk rewrite`, the source its hook
uses. The planted edit is the only difference from the clean repository, and it is undone after every run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .plant import Edit

PROJECTS = Path.home() / "Documents" / "Projects"
HERE = Path(__file__).resolve().parents[1]
ORACLE = PROJECTS / "oracle-mutants"
AUDITOR = PROJECTS / "auditor-mutants"
TOKO = PROJECTS / "toko-wa-bench"
WALEAD = PROJECTS / "wa-lead-extractor"
PY = HERE / "fixtures" / "py"
GO = HERE / "fixtures" / "go"


@dataclass(frozen=True)
class Case:
    id: str
    kind: str  # pytest | vitest | tsc | eslint | traceback | gotest
    repo: Path
    edits: tuple[Edit, ...]
    raw: tuple[str, ...]
    what: str  # the planted bug, in a few words


PYTEST = ("uv", "run", "pytest")
CASES: tuple[Case, ...] = (
    Case(
        "pytest-two",
        "pytest",
        ORACLE,
        (
            Edit(
                "src/oracle_mutants/operators.py",
                "bumped = str(int(token) + int(step))",
                "bumped = str(int(token) + int(step) + 1)",
            ),
        ),
        PYTEST,
        "an off-by-one when a number is shifted",
    ),
    Case(
        "pytest-many",
        "pytest",
        AUDITOR,
        (Edit("src/auditor_mutants/trace.py", '"time_ns": time + 1,', '"time_ns": time - 1,'),),
        ("uv", "run", "pytest"),
        "an end event stamped before its parent",
    ),
    Case(
        "pytest-collect",
        "pytest",
        ORACLE,
        (Edit("tests/test_probe.py", "def test_ladder_by_token_type():", "def test_ladder_by_token_type(:"),),
        PYTEST,
        "a syntax error in a test file",
    ),
    Case(
        "pytest-import",
        "pytest",
        TOKO,
        (
            Edit(
                "tests/test_tools.py",
                "from toko_wa.tools import TokoTools, normalize_phone\n",
                "from toko_wa.tools import TokoTools, normalize_courier, normalize_phone\n",
            ),
        ),
        ("uv", "run", "pytest", "-q"),
        "a test importing a name that does not exist",
    ),
    Case(
        "pytest-few",
        "pytest",
        TOKO,
        (
            Edit(
                "src/toko_wa/tools.py",
                "price_per_kg * max(1, math.ceil(weight_grams / 1000))",
                "price_per_kg * max(1, math.ceil(weight_grams / 1000)) + 1000",
            ),
        ),
        ("uv", "run", "pytest", "-q"),
        "a flat fee added to every shipping cost",
    ),
    Case(
        "traceback-deep",
        "traceback",
        PY,
        (Edit("orders.py", '{"sku": "celana-jeans-32", "qty": 1}', '{"sku": "celana-jeans-34", "qty": 1}'),),
        ("python3", "orders.py"),
        "an order for a product with no price",
    ),
    Case(
        "traceback-chained",
        "traceback",
        PY,
        (
            Edit(
                "settings.json",
                '{"warehouse": "Bandung", "courier": "JNE"}',
                '{"warehouse": "Bandung", "courier": "JNE",}',
            ),
        ),
        ("python3", "config_loader.py"),
        "a trailing comma in a settings file",
    ),
    Case(
        "gotest-one",
        "gotest",
        GO,
        (Edit("shipping.go", "kilos := (grams + 999) / 1000", "kilos := grams / 1000"),),
        ("go", "test", "./..."),
        "kilograms rounded down instead of up",
    ),
    Case(
        "gotest-panic",
        "gotest",
        GO,
        (Edit("shipping_test.go", 'Zone([]string{"40", "41"}, 1)', 'Zone([]string{"40", "41"}, 2)'),),
        ("go", "test", "./..."),
        "an index past the end of a slice",
    ),
    Case(
        "vitest-one",
        "vitest",
        WALEAD,
        (
            Edit(
                "src/qualify.ts",
                "export const BUDGET_FAR_BELOW_RATIO = 0.5;",
                "export const BUDGET_FAR_BELOW_RATIO = 0.9;",
            ),
        ),
        ("npx", "vitest", "run"),
        "a budget threshold set too high",
    ),
    Case(
        "tsc-one",
        "tsc",
        WALEAD,
        (
            Edit(
                "src/qualify.ts",
                "export const BUDGET_FAR_BELOW_RATIO = 0.5;",
                'export const BUDGET_FAR_BELOW_RATIO: number = "0.5";',
            ),
        ),
        ("npx", "tsc", "--noEmit"),
        "a string where a number belongs",
    ),
    Case(
        "pytest-renamed",
        "pytest",
        TOKO,
        (
            Edit(
                "src/toko_wa/tools.py",
                "    def _customer(self, customer_id: str) -> Customer:",
                "    def _get_customer(self, customer_id: str) -> Customer:",
            ),
        ),
        ("uv", "run", "pytest", "-q"),
        "a method renamed under its callers",
    ),
    Case(
        "vitest-many",
        "vitest",
        WALEAD,
        (
            Edit(
                "src/deterministic.ts",
                "export const JUTA_MULTIPLIER = 1_000_000;",
                "export const JUTA_MULTIPLIER = 100_000;",
            ),
        ),
        ("npx", "vitest", "run"),
        "a million written as a hundred thousand",
    ),
    Case(
        "tsc-many",
        "tsc",
        WALEAD,
        (
            Edit(
                "src/schema.ts", "  budgetIDR: z.number().nullable(),", "  budgetIdr: z.number().nullable(),"
            ),
        ),
        ("npx", "tsc", "--noEmit"),
        "a field renamed in the schema only",
    ),
    Case(
        "eslint-few",
        "eslint",
        WALEAD,
        (
            Edit(
                "src/qualify.ts",
                "export const BUDGET_FAR_BELOW_RATIO = 0.5;",
                "export const BUDGET_FAR_BELOW_RATIO = 0.5;\nconst unusedFloor = 1;\nlet neverRead = 2;",
            ),
        ),
        ("npx", "eslint", "--max-warnings=0", "src"),
        "two variables nobody reads",
    ),
    Case(
        "eslint-many",
        "eslint",
        WALEAD,
        (
            Edit(
                "src/classify.ts",
                "export function classifyLead(input: ClassifyInput): LeadState {",
                "let staleLabel = 'cold';\nconst unusedCutoff = 3;\nexport function classifyLead(input: ClassifyInput): LeadState {",
            ),
            Edit(
                "src/guardrail.ts",
                "export function sharedAreaCitation(",
                "let retryCount = 0;\nconst unusedLimit = 5;\nexport function sharedAreaCitation(",
            ),
            Edit(
                "src/merge.ts",
                "export function mergeProfile(deterministic: DeterministicResult, llmProfile: LeadProfile): LeadProfile {",
                "let lastMerge = '';\nconst unusedWeight = 0.5;\nexport function mergeProfile(deterministic: DeterministicResult, llmProfile: LeadProfile): LeadProfile {",
            ),
            Edit(
                "src/writer.ts",
                "export function makeLlmWriteFn(config: LlmConfig): WriteFn {",
                "let draftCount = 0;\nconst unusedTone = 'warm';\nexport function makeLlmWriteFn(config: LlmConfig): WriteFn {",
            ),
        ),
        ("npx", "eslint", "--max-warnings=0", "src"),
        "eight variables nobody reads, in four files",
    ),
)

# Added after the results, to test what rtk's pytest summary does when a run has errors and no failures.
# Not pre-registered; reported apart from the 16.
EXPLORATORY: tuple[Case, ...] = (
    Case(
        "pytest-setup-errors",
        "pytest",
        TOKO,
        (
            Edit(
                "tests/test_tools.py",
                "    return TokoTools(build())\n",
                '    return TokoTools(build(), currency="IDR")\n',
            ),
        ),
        ("uv", "run", "pytest", "-q"),
        "a fixture that cannot build its object",
    ),
)
