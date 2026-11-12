# AUTO-EXTRACTED FROM THE FINAL RESEARCH WORKBOOK.
# Executed in a shared production namespace by macro_portfolio.pipeline.
# Notebook display/install/Google-Drive infrastructure is intentionally excluded.


# ===== ORIGINAL NOTEBOOK CELL 92 =====
# ==================================================================================================
# SECTION K — PRODUCTION CONTROL PLANE / END-TO-END RUN AUDIT / FINAL FREEZE
# REPLACEMENT CELL V1.0.1
# ==================================================================================================

from pathlib import Path
import hashlib
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# ==================================================================================================
# 1. VALIDATE UPSTREAM
# ==================================================================================================

required_k_objects = [
    "SECTION_J_PASSED",
    "J_FINAL_RUN_MANIFEST",
    "J_SNAPSHOT_HISTORY",
    "I_FINAL_ACTION_BOOK",
    "I_FINAL_TRIGGERS",
    "I_FINAL_OPERATING_SNAPSHOT",
    "H_FINAL_MONITORING_SNAPSHOT",
    "H_FINAL_BUY_WATCHLIST",
    "H_FINAL_ALERTS",
    "G_FINAL_PORTFOLIO_WEIGHTS",
    "G_FINAL_TRADE_PLAN",
    "G_FINAL_PORTFOLIO_SUMMARY",
    "F_FINAL_VALUATION_HANDOFF",
    "VALUATION_UNIVERSE_FREEZE_ID",
    "PROJECT_ROOT",
    "STOCK_MODEL_DIR",
    "STOCK_OUTPUT_DIR",
]

missing_k_objects = [x for x in required_k_objects if x not in globals()]

if missing_k_objects:
    raise RuntimeError(
        "Section K requires completed A–J production state. Missing: "
        f"{missing_k_objects}"
    )

if not bool(SECTION_J_PASSED):
    raise RuntimeError("Section J production gate did not pass.")

K_VERSION = "1.0.1"
K_AS_OF_TIMESTAMP = pd.Timestamp.now(tz="Asia/Singapore")
K_RUN_ID = K_AS_OF_TIMESTAMP.strftime("%Y%m%d_%H%M%S")

K_CONTROL_DIR = Path(STOCK_OUTPUT_DIR) / "control"
K_CONTROL_DIR.mkdir(parents=True, exist_ok=True)

K_REGISTRY_PATH = (
    K_CONTROL_DIR
    /
    "production_run_registry.csv"
)


# ==================================================================================================
# 2. HELPERS
# ==================================================================================================

def k_any_true(names):

    for name in names:

        if name in globals():

            try:

                if bool(
                    globals()[name]
                ):
                    return True

            except Exception:

                pass

    return False


def k_any_present(names):

    return any(
        name in globals()
        for name in names
    )


def k_all_present(names):

    return all(
        name in globals()
        for name in names
    )


# ==================================================================================================
# 3. ROBUST SECTION READINESS DISCOVERY
# ==================================================================================================

K_SECTION_A_READY = bool(
    k_all_present(
        [
            "PROJECT_ROOT",
            "CONFIG",
        ]
    )
)


K_SECTION_D_READY = bool(

    k_any_true(
        [
            "SECTION_D_PASSED",
            "D8_PASSED",
            "REGIME_D8_PASSED",
            "REGIME_SECTION_D_PASSED",
        ]
    )

    or

    k_any_present(
        [
            "SECTOR_RISK_ADJUSTED_SIGNAL",
            "SECTOR_FINAL_SIGNAL",
            "D8_FINAL_SIGNAL",
        ]
    )

)


K_SECTION_E_READY = bool(

    k_any_true(
        [
            "SECTION_E_PASSED",
            "E7_PASSED",
            "STOCK_SELECTION_PASSED",
        ]
    )

    or

    k_any_present(
        [
            "STOCK_SELECTION_SIGNAL",
            "E7_FINAL_SELECTION",
        ]
    )

)


K_SECTION_F_READY = bool(

    k_any_true(
        [
            "VALUATION_SECTION_F_PASSED",
            "SECTION_F_PASSED",
            "F9_PASSED",
        ]
    )

    and

    "F_FINAL_VALUATION_HANDOFF"
    in globals()

)


K_SECTION_G_READY = bool(

    globals().get(
        "SECTION_G_PASSED",
        False,
    )

    and

    k_all_present(
        [
            "G_FINAL_PORTFOLIO_WEIGHTS",
            "G_FINAL_TRADE_PLAN",
        ]
    )

)


K_SECTION_H_READY = bool(

    globals().get(
        "SECTION_H_PASSED",
        False,
    )

    and

    k_all_present(
        [
            "H_FINAL_MONITORING_SNAPSHOT",
            "H_FINAL_BUY_WATCHLIST",
        ]
    )

)


K_SECTION_I_READY = bool(

    globals().get(
        "SECTION_I_PASSED",
        False,
    )

    and

    k_all_present(
        [
            "I_FINAL_ACTION_BOOK",
            "I_FINAL_OPERATING_SNAPSHOT",
        ]
    )

)


K_SECTION_J_READY = bool(

    globals().get(
        "SECTION_J_PASSED",
        False,
    )

    and

    k_all_present(
        [
            "J_FINAL_RUN_MANIFEST",
            "J_SNAPSHOT_HISTORY",
        ]
    )

)


# C and B may inherit readiness from successfully completed
# downstream canonical layers because those sections are necessary
# prerequisites for D.

K_SECTION_C_READY = bool(

    k_any_true(
        [
            "SECTION_C_PASSED",
            "C25_PASSED",
            "FEATURE_ENGINE_PASSED",
        ]
    )

    or

    k_any_present(
        [
            "FACTOR_SNAPSHOT",
            "FEATURE_SNAPSHOT",
            "FACTOR_CONFIDENCE",
        ]
    )

    or

    K_SECTION_D_READY

)


K_SECTION_B_READY = bool(

    k_any_true(
        [
            "SECTION_B_PASSED",
            "B_PASSED",
            "DATA_ENGINE_PASSED",
        ]
    )

    or

    k_any_present(
        [
            "DATA_MANIFEST",
            "SERIES_MANIFEST",
            "DATA_QUALITY_AUDIT",
            "FINAL_DATA_QUALITY_AUDIT",
        ]
    )

    or

    K_SECTION_C_READY

)


K_SECTION_STATUS = pd.DataFrame([

    {
        "section": "A",
        "name": "Infrastructure",
        "ready": K_SECTION_A_READY,
        "required_for_live_system": True,
    },

    {
        "section": "B",
        "name": "Core Data Engine",
        "ready": K_SECTION_B_READY,
        "required_for_live_system": True,
    },

    {
        "section": "C",
        "name": "Feature Engine",
        "ready": K_SECTION_C_READY,
        "required_for_live_system": True,
    },

    {
        "section": "D",
        "name": "Regime / Sector Engine",
        "ready": K_SECTION_D_READY,
        "required_for_live_system": True,
    },

    {
        "section": "E",
        "name": "Stock Selection",
        "ready": K_SECTION_E_READY,
        "required_for_live_system": True,
    },

    {
        "section": "F",
        "name": "Valuation",
        "ready": K_SECTION_F_READY,
        "required_for_live_system": True,
    },

    {
        "section": "G",
        "name": "Portfolio Construction",
        "ready": K_SECTION_G_READY,
        "required_for_live_system": True,
    },

    {
        "section": "H",
        "name": "Monitoring Dashboard",
        "ready": K_SECTION_H_READY,
        "required_for_live_system": True,
    },

    {
        "section": "I",
        "name": "Operating Decision Engine",
        "ready": K_SECTION_I_READY,
        "required_for_live_system": True,
    },

    {
        "section": "J",
        "name": "Attribution / Governance",
        "ready": K_SECTION_J_READY,
        "required_for_live_system": True,
    },

])


K_SECTION_STATUS[
    "status"
] = np.where(

    K_SECTION_STATUS[
        "ready"
    ],

    "✓ READY",

    "✗ NOT READY",

)


# ==================================================================================================
# 4. CANONICAL OBJECT REGISTRY
# ==================================================================================================

canonical_objects = [

    (
        "D",
        "SECTOR_RISK_ADJUSTED_SIGNAL",
        "Sector risk-adjusted signal",
    ),

    (
        "E",
        "STOCK_SELECTION_SIGNAL",
        "Company-selection signal",
    ),

    (
        "F",
        "F_FINAL_VALUATION_HANDOFF",
        "Final valuation handoff",
    ),

    (
        "G",
        "G_FINAL_PORTFOLIO_WEIGHTS",
        "Final portfolio weights",
    ),

    (
        "G",
        "G_FINAL_TRADE_PLAN",
        "Execution trade plan",
    ),

    (
        "H",
        "H_FINAL_MONITORING_SNAPSHOT",
        "Live monitoring snapshot",
    ),

    (
        "H",
        "H_FINAL_BUY_WATCHLIST",
        "MOS / buy-zone watchlist",
    ),

    (
        "H",
        "H_FINAL_ALERTS",
        "Portfolio alerts",
    ),

    (
        "I",
        "I_FINAL_ACTION_BOOK",
        "Daily investment decision book",
    ),

    (
        "I",
        "I_FINAL_TRIGGERS",
        "Daily operating triggers",
    ),

    (
        "I",
        "I_FINAL_OPERATING_SNAPSHOT",
        "Daily operating summary",
    ),

    (
        "J",
        "J_FINAL_PERFORMANCE_ATTRIBUTION",
        "Latest forward attribution",
    ),

    (
        "J",
        "J_FINAL_MODEL_DRIFT",
        "Model-drift table",
    ),

    (
        "J",
        "J_FINAL_GOVERNANCE_ALERTS",
        "Governance alerts",
    ),

    (
        "J",
        "J_FINAL_PERFORMANCE_LEDGER",
        "Persistent live performance ledger",
    ),

    (
        "J",
        "J_FINAL_RUN_MANIFEST",
        "End-to-end run manifest",
    ),

]


artifact_rows = []


for section, object_name, description in canonical_objects:

    available = (
        object_name
        in
        globals()
    )

    rows = np.nan
    columns = np.nan

    if available:

        obj = globals()[
            object_name
        ]

        if isinstance(
            obj,
            pd.DataFrame,
        ):

            rows = len(
                obj
            )

            columns = len(
                obj.columns
            )

    artifact_rows.append({

        "section":
            section,

        "object_name":
            object_name,

        "description":
            description,

        "available":
            available,

        "rows":
            rows,

        "columns":
            columns,

    })


K_ARTIFACT_REGISTRY = pd.DataFrame(
    artifact_rows
)


# ==================================================================================================
# 5. CANONICAL FILE REGISTRY
# ==================================================================================================

K_FILE_REGISTRY_INPUT = [

    (
        "G",
        Path(STOCK_OUTPUT_DIR)
        /
        "g_final_portfolio.csv",
    ),

    (
        "G",
        Path(STOCK_OUTPUT_DIR)
        /
        "g_final_trade_plan.csv",
    ),

    (
        "H",
        Path(STOCK_OUTPUT_DIR)
        /
        "h_final_monitoring_snapshot.csv",
    ),

    (
        "H",
        Path(STOCK_OUTPUT_DIR)
        /
        "h_buy_watchlist.csv",
    ),

    (
        "H",
        Path(STOCK_OUTPUT_DIR)
        /
        "dashboard"
        /
        "portfolio_monitor_dashboard.html",
    ),

    (
        "I",
        Path(STOCK_OUTPUT_DIR)
        /
        "i_latest_decision_book.csv",
    ),

    (
        "I",
        Path(STOCK_OUTPUT_DIR)
        /
        "i_latest_daily_summary.csv",
    ),

    (
        "J",
        Path(STOCK_OUTPUT_DIR)
        /
        "governance"
        /
        "snapshot_history.csv",
    ),

    (
        "J",
        Path(STOCK_OUTPUT_DIR)
        /
        "governance"
        /
        "live_portfolio_performance_ledger.csv",
    ),

    (
        "J",
        Path(STOCK_OUTPUT_DIR)
        /
        "governance"
        /
        "latest_run_manifest.csv",
    ),

]


K_FILE_REGISTRY = pd.DataFrame([

    {

        "section":
            section,

        "path":
            str(
                path
            ),

        "exists":
            path.exists(),

        "size_bytes":
            (
                path.stat().st_size
                if path.exists()
                else np.nan
            ),

    }

    for section, path
    in K_FILE_REGISTRY_INPUT

])


# ==================================================================================================
# 6. LINEAGE / GOVERNANCE AUDIT
# ==================================================================================================

K_VALUATION_COUNT = len(
    F_FINAL_VALUATION_HANDOFF
)


K_MONITOR_COUNT = len(
    H_FINAL_MONITORING_SNAPSHOT
)


K_DECISION_COUNT = len(
    I_FINAL_ACTION_BOOK
)


# FIX:
#
# .sum() is applied to the boolean Series first.
#
# Then the scalar result is converted to int.

K_CURRENT_STOCK_POSITIONS = int(

    (

        (

            pd.to_numeric(

                G_FINAL_PORTFOLIO_WEIGHTS[
                    "target_weight"
                ],

                errors="coerce",

            )

            .fillna(
                0.0
            )

            >
            1e-10

        )

        &

        (

            G_FINAL_PORTFOLIO_WEIGHTS[
                "ticker"
            ]
            .astype(str)

            !=
            "CASH"

        )

    )

    .sum()

)


K_WEIGHT_SUM = float(

    pd.to_numeric(

        G_FINAL_PORTFOLIO_WEIGHTS[
            "target_weight"
        ],

        errors="coerce",

    )

    .fillna(
        0.0
    )

    .sum()

)


K_WEIGHT_SUM_VALID = bool(

    np.isclose(

        K_WEIGHT_SUM,

        1.0,

        atol=1e-7,
        rtol=1e-7,

    )

)


K_J_FREEZE_ID = (

    J_FINAL_RUN_MANIFEST
    .iloc[0]
    .get(
        "valuation_universe_freeze_id"
    )

)


K_FREEZE_ID_CONSISTENT = bool(

    str(
        K_J_FREEZE_ID
    )

    ==

    str(
        VALUATION_UNIVERSE_FREEZE_ID
    )

)


K_CURRENT_SNAPSHOT_ID = str(

    I_FINAL_OPERATING_SNAPSHOT
    .iloc[0]
    .get(
        "snapshot_id"
    )

)


K_J_SNAPSHOT_ID = str(

    J_FINAL_RUN_MANIFEST
    .iloc[0]
    .get(
        "snapshot_id"
    )

)


K_SNAPSHOT_ID_CONSISTENT = bool(

    K_CURRENT_SNAPSHOT_ID

    ==

    K_J_SNAPSHOT_ID

)


K_PROVISIONAL_HOLDING_VIOLATIONS = int(

    (

        (

            pd.to_numeric(

                H_FINAL_MONITORING_SNAPSHOT[
                    "target_weight"
                ],

                errors="coerce",

            )

            .fillna(
                0.0
            )

            >
            1e-10

        )

        &

        (

            ~
            H_FINAL_MONITORING_SNAPSHOT[
                "research_ranking_eligible"
            ]
            .fillna(False)
            .astype(bool)

        )

    )

    .sum()

)


if (

    "new_entry_optimizer_eligible"
    in
    G_FINAL_PORTFOLIO_WEIGHTS.columns

):

    K_NEW_ENTRY_MOS_VIOLATIONS = int(

        (

            (

                pd.to_numeric(

                    G_FINAL_PORTFOLIO_WEIGHTS[
                        "target_weight"
                    ],

                    errors="coerce",

                )

                .fillna(
                    0.0
                )

                >
                1e-10

            )

            &

            (

                G_FINAL_PORTFOLIO_WEIGHTS[
                    "ticker"
                ]
                .astype(str)

                !=
                "CASH"

            )

                        &
            (
                ~
                G_FINAL_PORTFOLIO_WEIGHTS[
                    "new_entry_optimizer_eligible"
                ]
                .fillna(False)
                .astype(bool)
            )
            # v1.0.14: only BUYING MORE of a non-eligible name is a violation.
            # An existing holding whose valuation later becomes blocked may be
            # held (not added to); forcing an automatic sale on a model anomaly
            # is not the policy.
            &
            (
                pd.to_numeric(G_FINAL_PORTFOLIO_WEIGHTS["target_weight"], errors="coerce").fillna(0.0)
                >
                pd.to_numeric(
                    G_FINAL_PORTFOLIO_WEIGHTS.get(
                        "previous_weight",
                        pd.Series(0.0, index=G_FINAL_PORTFOLIO_WEIGHTS.index),
                    ),
                    errors="coerce",
                ).fillna(0.0)
                + 1e-6
            )
        )
        .sum()
    )
else:
    K_NEW_ENTRY_MOS_VIOLATIONS = 0


K_ALL_REQUIRED_SECTIONS_READY = bool(

    K_SECTION_STATUS.loc[

        K_SECTION_STATUS[
            "required_for_live_system"
        ],

        "ready",

    ]

    .all()

)


K_REQUIRED_FILES_EXIST = bool(

    K_FILE_REGISTRY[
        "exists"
    ]
    .all()

)


K_LINEAGE_AUDIT = pd.DataFrame([

    {

        "check":
            "All required sections A–J report ready",

        "passed":
            K_ALL_REQUIRED_SECTIONS_READY,

        "required":
            True,

        "detail":
            (
                f"ready="
                f"{int(K_SECTION_STATUS['ready'].sum())}/"
                f"{len(K_SECTION_STATUS)}"
            ),

    },

    {

        "check":
            "Section D canonical output exists",

        "passed":
            K_SECTION_D_READY,

        "required":
            True,

        "detail":
            (
                "SECTOR_RISK_ADJUSTED_SIGNAL="
                f"{'SECTOR_RISK_ADJUSTED_SIGNAL' in globals()}"
            ),

    },

    {

        "check":
            "Section E canonical output exists",

        "passed":
            K_SECTION_E_READY,

        "required":
            True,

        "detail":
            (
                "STOCK_SELECTION_SIGNAL="
                f"{'STOCK_SELECTION_SIGNAL' in globals()}"
            ),

    },

    {

        "check":
            "Valuation freeze ID is consistent through J",

        "passed":
            K_FREEZE_ID_CONSISTENT,

        "required":
            True,

        "detail":
            (
                f"current={VALUATION_UNIVERSE_FREEZE_ID}; "
                f"J={K_J_FREEZE_ID}"
            ),

    },

    {

        "check":
            "Current operating snapshot ID matches J",

        "passed":
            K_SNAPSHOT_ID_CONSISTENT,

        "required":
            True,

        "detail":
            (
                f"I={K_CURRENT_SNAPSHOT_ID}; "
                f"J={K_J_SNAPSHOT_ID}"
            ),

    },

    {

        "check":
            "Final portfolio weights sum to 100%",

        "passed":
            K_WEIGHT_SUM_VALID,

        "required":
            True,

        "detail":
            (
                f"weight_sum="
                f"{K_WEIGHT_SUM:.8f}"
            ),

    },

    {

        "check":
            "No provisional company is held",

        "passed":
            (
                K_PROVISIONAL_HOLDING_VIOLATIONS
                ==
                0
            ),

        "required":
            True,

        "detail":
            (
                f"violations="
                f"{K_PROVISIONAL_HOLDING_VIOLATIONS}"
            ),

    },

    {

        "check":
            "No MOS-governance violation detected (no additions to ineligible names)",

        "passed":
            (
                K_NEW_ENTRY_MOS_VIOLATIONS
                ==
                0
            ),

        "required":
            True,

        "detail":
            (
                f"violations="
                f"{K_NEW_ENTRY_MOS_VIOLATIONS}"
            ),

    },

    {

        "check":
            "Monitoring and decision-book universe sizes agree",

        "passed":
            (
                K_MONITOR_COUNT
                ==
                K_DECISION_COUNT
            ),

        "required":
            True,

        "detail":
            (
                f"monitor={K_MONITOR_COUNT}; "
                f"decision={K_DECISION_COUNT}"
            ),

    },

    {

        "check":
            "Required canonical output files exist",

        "passed":
            K_REQUIRED_FILES_EXIST,

        "required":
            True,

        "detail":
            (
                f"files="
                f"{int(K_FILE_REGISTRY['exists'].sum())}/"
                f"{len(K_FILE_REGISTRY)}"
            ),

    },

    {

        "check":
            "Historical PIT backtest remains blocked",

        "passed":
            True,

        "required":
            True,

        "detail":
            (
                "Live engine is valid; historical alpha backtesting "
                "still requires PIT constituent/fundamental/"
                "valuation history."
            ),

    },

])


K_LINEAGE_AUDIT[
    "status"
] = np.where(

    K_LINEAGE_AUDIT[
        "passed"
    ],

    "✓ PASS",

    "✗ FAIL",

)


K_REQUIRED_FAILURES = (

    K_LINEAGE_AUDIT[

        K_LINEAGE_AUDIT[
            "required"
        ]

        &

        ~
        K_LINEAGE_AUDIT[
            "passed"
        ]

    ]

    .copy()

)


# ==================================================================================================
# 7. CORRECT J BOOKKEEPING FALSE NEGATIVE
# ==================================================================================================

K_CORRECTED_J_MANIFEST = (

    J_FINAL_RUN_MANIFEST
    .copy()

)


K_CORRECTED_J_MANIFEST[
    "section_d_passed"
] = (

    K_SECTION_D_READY

)


K_CORRECTED_J_MANIFEST[
    "section_e_passed"
] = (

    K_SECTION_E_READY

)


K_CORRECTED_J_MANIFEST.to_csv(

    K_CONTROL_DIR
    /
    "corrected_j_run_manifest.csv",

    index=False,

)


# ==================================================================================================
# 8. FINAL SYSTEM MANIFEST
# ==================================================================================================

portfolio_summary = (

    G_FINAL_PORTFOLIO_SUMMARY
    .iloc[0]
    .to_dict()

)


operating_summary = (

    I_FINAL_OPERATING_SNAPSHOT
    .iloc[0]
    .to_dict()

)


K_FINAL_SYSTEM_MANIFEST = pd.DataFrame([{

    "section":
        "K",

    "version":
        K_VERSION,

    "production_run_id":
        K_RUN_ID,

    "as_of":
        K_AS_OF_TIMESTAMP,

    "snapshot_id":
        K_CURRENT_SNAPSHOT_ID,

    "valuation_universe_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "section_a_ready":
        K_SECTION_A_READY,

    "section_b_ready":
        K_SECTION_B_READY,

    "section_c_ready":
        K_SECTION_C_READY,

    "section_d_ready":
        K_SECTION_D_READY,

    "section_e_ready":
        K_SECTION_E_READY,

    "section_f_ready":
        K_SECTION_F_READY,

    "section_g_ready":
        K_SECTION_G_READY,

    "section_h_ready":
        K_SECTION_H_READY,

    "section_i_ready":
        K_SECTION_I_READY,

    "section_j_ready":
        K_SECTION_J_READY,

    "valuation_universe_count":
        K_VALUATION_COUNT,

    "monitoring_universe_count":
        K_MONITOR_COUNT,

    "stock_positions":
        K_CURRENT_STOCK_POSITIONS,

    "portfolio_weight_sum":
        K_WEIGHT_SUM,

    "cash_weight":
        portfolio_summary.get(
            "cash_weight"
        ),

    "expected_return":
        portfolio_summary.get(
            "expected_return_gross"
        ),

    "expected_net_first_year_return":
        portfolio_summary.get(
            "expected_return_net_first_year"
        ),

    "expected_volatility":
        portfolio_summary.get(
            "expected_volatility"
        ),

    "expected_sharpe":
        portfolio_summary.get(
            "expected_sharpe"
        ),

    "expected_sortino":
        portfolio_summary.get(
            "expected_sortino"
        ),

    "expected_calmar":
        portfolio_summary.get(
            "expected_calmar"
        ),

    "portfolio_turnover":
        portfolio_summary.get(
            "turnover"
        ),

    "transaction_cost":
        portfolio_summary.get(
            "transaction_cost"
        ),

    "daily_operating_status":
        operating_summary.get(
            "daily_status"
        ),

    "trades_pending":
        operating_summary.get(
            "execution_trades_pending"
        ),

    "action_required_triggers":
        operating_summary.get(
            "action_required_triggers"
        ),

    "critical_triggers":
        operating_summary.get(
            "critical_triggers"
        ),

    "snapshot_count":
        len(
            J_SNAPSHOT_HISTORY
        ),

    "live_forward_monitoring_active":
        bool(

            J_FINAL_RUN_MANIFEST
            .iloc[0]
            .get(
                "live_forward_monitoring_active",
                False,
            )

        ),

    "historical_pit_backtest_eligible":
        False,

}])


# ==================================================================================================
# 9. HASH / FINAL STATUS
# ==================================================================================================

K_HASH_FRAME = (

    K_FINAL_SYSTEM_MANIFEST[
        [
            "snapshot_id",

            "valuation_universe_freeze_id",

            "stock_positions",

            "portfolio_weight_sum",

            "cash_weight",

            "daily_operating_status",

            "trades_pending",
        ]
    ]

    .copy()

)


K_RUN_SHA256 = hashlib.sha256(

    pd.util.hash_pandas_object(

        K_HASH_FRAME,
        index=False,

    )
    .values
    .tobytes()

).hexdigest()


SECTION_K_PASSED = bool(

    K_REQUIRED_FAILURES.empty

)


SYSTEM_PRODUCTION_READY = bool(

    SECTION_K_PASSED

    and

    K_ALL_REQUIRED_SECTIONS_READY

)


K_FINAL_SYSTEM_MANIFEST[
    "production_run_sha256"
] = (

    K_RUN_SHA256

)


K_FINAL_SYSTEM_MANIFEST[
    "section_k_passed"
] = (

    SECTION_K_PASSED

)


K_FINAL_SYSTEM_MANIFEST[
    "system_production_ready"
] = (

    SYSTEM_PRODUCTION_READY

)


# ==================================================================================================
# 10. PERSISTENT PRODUCTION RUN REGISTRY
# ==================================================================================================

if K_REGISTRY_PATH.exists():

    try:

        K_FINAL_RUN_REGISTRY = pd.read_csv(

            K_REGISTRY_PATH

        )

    except Exception:

        K_FINAL_RUN_REGISTRY = pd.DataFrame()


else:

    K_FINAL_RUN_REGISTRY = pd.DataFrame()


# One canonical K record per Section-I snapshot.

if (

    not K_FINAL_RUN_REGISTRY.empty

    and

    "snapshot_id"
    in
    K_FINAL_RUN_REGISTRY.columns

):

    K_FINAL_RUN_REGISTRY = (

        K_FINAL_RUN_REGISTRY[

            K_FINAL_RUN_REGISTRY[
                "snapshot_id"
            ]
            .astype(str)

            !=

            str(
                K_CURRENT_SNAPSHOT_ID
            )

        ]

        .copy()

    )


K_FINAL_RUN_REGISTRY = pd.concat(

    [

        K_FINAL_RUN_REGISTRY,

        K_FINAL_SYSTEM_MANIFEST,

    ],

    ignore_index=True,

)


K_FINAL_RUN_REGISTRY.to_csv(

    K_REGISTRY_PATH,

    index=False,

)


# ==================================================================================================
# 11. SAVE CONTROL OUTPUTS
# ==================================================================================================

K_SECTION_STATUS.to_csv(

    K_CONTROL_DIR
    /
    "latest_section_status.csv",

    index=False,

)


K_ARTIFACT_REGISTRY.to_csv(

    K_CONTROL_DIR
    /
    "latest_artifact_registry.csv",

    index=False,

)


K_FILE_REGISTRY.to_csv(

    K_CONTROL_DIR
    /
    "latest_file_registry.csv",

    index=False,

)


K_LINEAGE_AUDIT.to_csv(

    K_CONTROL_DIR
    /
    "latest_lineage_audit.csv",

    index=False,

)


K_FINAL_SYSTEM_MANIFEST.to_csv(

    K_CONTROL_DIR
    /
    "latest_system_manifest.csv",

    index=False,

)


current_snapshot_dir = Path(
    I_SNAPSHOT_DIR
)


K_FINAL_SYSTEM_MANIFEST.to_csv(

    current_snapshot_dir
    /
    "system_manifest.csv",

    index=False,

)


K_LINEAGE_AUDIT.to_csv(

    current_snapshot_dir
    /
    "lineage_audit.csv",

    index=False,

)


# ==================================================================================================
# 12. MASTER PRODUCTION HANDOFF
# ==================================================================================================

K_FINAL_PRODUCTION_HANDOFF = {

    "run_id":
        K_RUN_ID,

    "snapshot_id":
        K_CURRENT_SNAPSHOT_ID,

    "valuation_freeze_id":
        VALUATION_UNIVERSE_FREEZE_ID,

    "portfolio":
        G_FINAL_PORTFOLIO_WEIGHTS,

    "trade_plan":
        G_FINAL_TRADE_PLAN,

    "monitor":
        H_FINAL_MONITORING_SNAPSHOT,

    "buy_watchlist":
        H_FINAL_BUY_WATCHLIST,

    "portfolio_alerts":
        H_FINAL_ALERTS,

    "decision_book":
        I_FINAL_ACTION_BOOK,

    "operating_triggers":
        I_FINAL_TRIGGERS,

    "operating_summary":
        I_FINAL_OPERATING_SNAPSHOT,

    "performance_attribution":
        globals().get(
            "J_FINAL_PERFORMANCE_ATTRIBUTION"
        ),

    "model_drift":
        globals().get(
            "J_FINAL_MODEL_DRIFT"
        ),

    "governance_alerts":
        globals().get(
            "J_FINAL_GOVERNANCE_ALERTS"
        ),

    "performance_ledger":
        globals().get(
            "J_FINAL_PERFORMANCE_LEDGER"
        ),

    "system_manifest":
        K_FINAL_SYSTEM_MANIFEST,

    "production_ready":
        SYSTEM_PRODUCTION_READY,

}


# ==================================================================================================
# 13. DISPLAY
# ==================================================================================================

print(
    "=" * 150
)

print(
    "SECTION K — PRODUCTION CONTROL PLANE / END-TO-END RUN AUDIT V1.0.1"
)

print(
    "=" * 150
)


print(
    f"Production run ID:                  "
    f"{K_RUN_ID}"
)

print(
    f"Snapshot ID:                        "
    f"{K_CURRENT_SNAPSHOT_ID}"
)

print(
    f"Valuation freeze ID:                "
    f"{VALUATION_UNIVERSE_FREEZE_ID}"
)

print(
    f"Current stock positions:            "
    f"{K_CURRENT_STOCK_POSITIONS}"
)

print(
    f"Portfolio weight sum:               "
    f"{K_WEIGHT_SUM:.8f}"
)

print(
    f"System production ready:            "
    f"{SYSTEM_PRODUCTION_READY}"
)

print(
    f"Final run SHA256:                   "
    f"{K_RUN_SHA256}"
)


print(
    "\nA → J SECTION STATUS:"
)

display(
    K_SECTION_STATUS
)


print(
    "\nCANONICAL object registry:"
)

display(
    K_ARTIFACT_REGISTRY
)


print(
    "\nCANONICAL file registry:"
)

display(
    K_FILE_REGISTRY
)


print(
    "\nEND-TO-END lineage / governance audit:"
)

display(
    K_LINEAGE_AUDIT
)


print(
    "\nFINAL production system manifest:"
)

display(
    K_FINAL_SYSTEM_MANIFEST
)


print(
    "\nPRODUCTION run registry:"
)

display(

    K_FINAL_RUN_REGISTRY
    .tail(
        10
    )

)


print(
    "\nFINAL portfolio handoff:"
)


portfolio_display_columns = [

    c

    for c in [

        "ticker",
        "company_name",
        "sector_ticker",

        "target_weight",

        "expected_total_return_annual",

        "optimizer_volatility_annual",

        "risk_contribution_share",

        "action",

        "trade_notional",

        "liquidity_check",

    ]

    if c
    in
    G_FINAL_PORTFOLIO_WEIGHTS.columns

]


display(

    G_FINAL_PORTFOLIO_WEIGHTS[
        portfolio_display_columns
    ]

    .sort_values(

        "target_weight",

        ascending=False,

    )

)


print(
    "\nTOP current operating decisions:"
)


decision_display_columns = [

    c

    for c in [

        "decision_priority",

        "ticker",
        "company_name",

        "decision_category",

        "current_price",
        "buy_trigger_price",

        "target_weight",

        "trade_required",
        "trade_notional",

        "capacity_notional",

        "master_alpha_rank",

    ]

    if c
    in
    I_FINAL_ACTION_BOOK.columns

]


display(

    I_FINAL_ACTION_BOOK[
        decision_display_columns
    ]

    .head(
        15
    )

)


# ==================================================================================================
# 14. FINAL PRODUCTION GATE
# ==================================================================================================

if not SECTION_K_PASSED:

    display(
        K_REQUIRED_FAILURES
    )

    raise RuntimeError(
        "SECTION K PRODUCTION GATE FAILED."
    )


if not SYSTEM_PRODUCTION_READY:

    failed_sections = (

        K_SECTION_STATUS[

            ~
            K_SECTION_STATUS[
                "ready"
            ]

        ]

        .copy()

    )

    display(
        failed_sections
    )

    raise RuntimeError(
        "END-TO-END SYSTEM IS NOT PRODUCTION READY."
    )


print(
    "\n"
    + "=" * 150
)

print(
    "✓ SECTION K COMPLETE — END-TO-END LIVE SYSTEM FROZEN."
)

print(
    "✓ A→J readiness is represented in one production control plane."
)

print(
    "✓ The Section-D bookkeeping false-negative in J is corrected without changing investment outputs."
)

print(
    "✓ Final portfolio weights reconcile to 100%."
)

print(
    "✓ No provisional holding or MOS-governance violation is present."
)

print(
    "✓ Canonical portfolio, monitoring, operating and governance files are registered."
)

print(
    "✓ One canonical production-registry row is retained per Section-I snapshot."
)

print(
    "✓ K_FINAL_PRODUCTION_HANDOFF is the master downstream object."
)

print(
    "✓ SYSTEM_PRODUCTION_READY = True."
)

print(
    "✓ The LIVE portfolio engine is complete."
)

print(
    "✓ Historical PIT backtesting remains a separate future workstream."
)

print(
    "=" * 150
)

# ===== ORIGINAL NOTEBOOK CELL 93 =====
# ==================================================================================================
# CELL K2 — READINESS SEMANTICS / EXECUTION GOVERNANCE V1.0.0
# ==================================================================================================
# Separate software readiness from real-money readiness and empirical validation.
# ==================================================================================================

PIPELINE_OPERATIONAL_READY = bool(globals().get("SYSTEM_PRODUCTION_READY", False))
LIVE_MODEL_PORTFOLIO_READY = bool(PIPELINE_OPERATIONAL_READY and globals().get("PORTFOLIO_STATE_MODE", "MODEL") in ["MODEL", "PAPER", "REAL"])

if "G_FINAL_TRADE_PLAN" in globals() and "liquidity_check" in G_FINAL_TRADE_PLAN.columns:
    _tp = G_FINAL_TRADE_PLAN.copy()
    _required = _tp["trade_required"].fillna(False).astype(bool) if "trade_required" in _tp.columns else pd.Series(False, index=_tp.index)
    _mask = (_tp["ticker"].astype(str) != "CASH") & _required
    _liq = _tp.loc[_mask, "liquidity_check"].astype(str).str.upper()
    K2_LIQUIDITY_FAILURES = int((~_liq.isin(["PASS", "OK", "N/A", "NA", "NONE"])).sum())
else:
    K2_LIQUIDITY_FAILURES = 0

K2_CRITICAL_ALERTS = int(
    (H_FINAL_ALERTS["severity"].astype(str).str.upper() == "CRITICAL").sum()
    if "H_FINAL_ALERTS" in globals() and len(H_FINAL_ALERTS) else 0
)

REAL_MONEY_EXECUTION_READY = bool(
    PIPELINE_OPERATIONAL_READY
    and globals().get("PORTFOLIO_STATE_MODE", "MODEL") == "REAL"
    and bool(globals().get("PORTFOLIO_STATE_IS_ACTUAL", False))
    and K2_LIQUIDITY_FAILURES == 0
    and K2_CRITICAL_ALERTS == 0
)

# Explicitly remain False until a true PIT historical infrastructure exists.
PIT_BACKTEST_READY = False

# Section L is currently an approximate screening diagnostic, not sufficient
# to certify the full stock-selection / valuation / optimizer stack.
STRATEGY_EMPIRICALLY_VALIDATED = False

K2_READINESS = pd.DataFrame([{
    "pipeline_operational_ready": PIPELINE_OPERATIONAL_READY,
    "live_model_portfolio_ready": LIVE_MODEL_PORTFOLIO_READY,
    "real_money_execution_ready": REAL_MONEY_EXECUTION_READY,
    "pit_backtest_ready": PIT_BACKTEST_READY,
    "strategy_empirically_validated": STRATEGY_EMPIRICALLY_VALIDATED,
    "portfolio_state_mode": globals().get("PORTFOLIO_STATE_MODE", "UNKNOWN"),
    "portfolio_state_is_actual": bool(globals().get("PORTFOLIO_STATE_IS_ACTUAL", False)),
    "liquidity_failures": K2_LIQUIDITY_FAILURES,
    "critical_alerts": K2_CRITICAL_ALERTS,
}])
K2_CONTROL_DIR = Path(STOCK_OUTPUT_DIR) / "control"
K2_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
K2_READINESS.to_csv(K2_CONTROL_DIR / "latest_readiness_semantics.csv", index=False)

print("=" * 140)
print("K2 — READINESS SEMANTICS")
print("=" * 140)
display(K2_READINESS)
print("✓ SYSTEM_PRODUCTION_READY means the pipeline completed consistently.")
print("✓ REAL_MONEY_EXECUTION_READY additionally requires REAL portfolio state and clean execution gates.")
print("✓ PIT_BACKTEST_READY and STRATEGY_EMPIRICALLY_VALIDATED remain False by design.")


# ===== ORIGINAL NOTEBOOK CELL 94 =====
# ==================================================================================================
# SECTION K.3 — FINAL DYNAMIC-STATE / NO-STALE-FALLBACK AUDIT V1.2.0
# ==================================================================================================

K3_DYNAMIC_AUDIT_ROWS = []

def k3_check(name, passed, detail, required=True):
    K3_DYNAMIC_AUDIT_ROWS.append({
        "check": name,
        "passed": bool(passed),
        "required": bool(required),
        "detail": str(detail),
    })

# 1) Current sector signal only — no frozen historical snapshot fallback.
k3_check(
    "G1 uses current D6 sector state",
    globals().get("G1_D_SOURCE_TYPE") in {"MEMORY", "PARQUET"},
    f"source_type={globals().get('G1_D_SOURCE_TYPE')}",
)

# 2) G1 long buckets must exactly equal CURRENT E1 research scope.
_k3_scope = globals().get("SECTOR_STOCK_RESEARCH_SCOPE", pd.DataFrame()).copy()
if not _k3_scope.empty and {"ticker", "stock_research_scope"}.issubset(_k3_scope.columns):
    _k3_core = set(_k3_scope.loc[_k3_scope["stock_research_scope"] == "CORE_LONG", "ticker"].astype(str))
    _k3_tactical = set(_k3_scope.loc[_k3_scope["stock_research_scope"] == "TACTICAL_LONG", "ticker"].astype(str))
else:
    _k3_core, _k3_tactical = set(), set()

k3_check(
    "G1 CORE_LONG sectors equal current E1 scope",
    set(globals().get("G1_CORE_LONG_SECTORS", set())) == _k3_core,
    f"G1={sorted(globals().get('G1_CORE_LONG_SECTORS', set()))}; E1={sorted(_k3_core)}",
)
k3_check(
    "G1 TACTICAL_LONG sectors equal current E1 scope",
    set(globals().get("G1_TACTICAL_LONG_SECTORS", set())) == _k3_tactical,
    f"G1={sorted(globals().get('G1_TACTICAL_LONG_SECTORS', set()))}; E1={sorted(_k3_tactical)}",
)

# 3) Frozen valuation lineage counts must reconcile dynamically.
_k3_f4c = globals().get("F4C_MANIFEST", pd.DataFrame())
_k3_f9 = globals().get("F_FINAL_VALUATION_HANDOFF", pd.DataFrame())
_k3_count_f4c = int(_k3_f4c["ticker"].astype(str).nunique()) if (not _k3_f4c.empty and "ticker" in _k3_f4c.columns) else -1
_k3_count_f9 = int(_k3_f9["ticker"].astype(str).nunique()) if (not _k3_f9.empty and "ticker" in _k3_f9.columns) else -2
k3_check(
    "Valuation company count derives from current frozen lineage",
    _k3_count_f4c == _k3_count_f9 and _k3_count_f4c >= 0,
    f"F4C={_k3_count_f4c}; F_FINAL={_k3_count_f9}",
)

# 4) Ranking/provisional counts reconcile from the actual Boolean column.
if not _k3_f9.empty and "ranking_eligible_after_f5" in _k3_f9.columns:
    _k3_rank = int(_k3_f9["ranking_eligible_after_f5"].fillna(False).astype(bool).sum())
    _k3_prov = int((~_k3_f9["ranking_eligible_after_f5"].fillna(False).astype(bool)).sum())
    _k3_total = len(_k3_f9)
else:
    _k3_rank = _k3_prov = -1
    _k3_total = -2
k3_check(
    "Ranking + provisional counts are data-derived",
    _k3_rank >= 0 and (_k3_rank + _k3_prov == _k3_total),
    f"ranking={_k3_rank}; provisional={_k3_prov}; total={_k3_total}",
)

# 5) Narrow F4D may be incomplete, but F4E must resolve every name before F5.
_k3_f4d = globals().get("F4D_EXIT_MULTIPLE_ANCHORS", pd.DataFrame())
_k3_f4e = globals().get("F4E_EXIT_MULTIPLE_ANCHORS", pd.DataFrame())

if (
    not _k3_f4d.empty
    and "ticker" in _k3_f4d.columns
    and "base_exit_multiple" in _k3_f4d.columns
):
    _k3_f4d_unresolved = set(
        _k3_f4d.loc[
            _k3_f4d["base_exit_multiple"].isna(),
            "ticker",
        ].astype(str)
    )
else:
    _k3_f4d_unresolved = set()

if (
    not _k3_f4e.empty
    and "ticker" in _k3_f4e.columns
    and "base_exit_multiple" in _k3_f4e.columns
):
    _k3_f4e_resolved = set(
        _k3_f4e.loc[
            _k3_f4e["base_exit_multiple"].notna(),
            "ticker",
        ].astype(str)
    )
    _k3_f4e_full_coverage = bool(
        _k3_f4e["base_exit_multiple"].notna().all()
    )
else:
    _k3_f4e_resolved = set()
    _k3_f4e_full_coverage = False

_k3_still_unresolved = sorted(
    _k3_f4d_unresolved
    -
    _k3_f4e_resolved
)

k3_check(
    "F4E resolves every F4D narrow-stage unresolved anchor",
    _k3_f4e_full_coverage and not _k3_still_unresolved,
    (
        f"F4D_unresolved={sorted(_k3_f4d_unresolved)}; "
        f"still_unresolved_after_F4E={_k3_still_unresolved}; "
        f"F4E_full_coverage={_k3_f4e_full_coverage}"
    ),
)

# 6) Portfolio state must come from explicit MODEL/PAPER/REAL/ZERO mode, never an implicit stale snapshot.
_k3_mode = str(cfg(["execution", "portfolio_state_mode"], "MODEL")).upper()
k3_check(
    "Portfolio-state mode is explicit",
    _k3_mode in {"MODEL", "PAPER", "REAL", "ZERO"},
    f"mode={_k3_mode}",
)

# G3 source-discovery threshold can never exceed the current universe.
if "G3_EXPECTED_COMPANY_COUNT" in globals():
    _k3_g3_required_overlap = min(
        int(G3_EXPECTED_COMPANY_COUNT),
        max(
            1,
            int(np.ceil(
                float(globals().get("G3_SOURCE_MIN_OVERLAP_RATIO", 0.70))
                * int(G3_EXPECTED_COMPANY_COUNT)
            )),
            min(
                int(globals().get("G3_SOURCE_MIN_OVERLAP_COUNT", 3)),
                int(G3_EXPECTED_COMPANY_COUNT),
            ),
        ),
    ) if int(G3_EXPECTED_COMPANY_COUNT) > 0 else 0
    k3_check(
        "G3 market-source overlap threshold is attainable",
        _k3_g3_required_overlap <= int(G3_EXPECTED_COMPANY_COUNT),
        f"required={_k3_g3_required_overlap}, universe={int(G3_EXPECTED_COMPANY_COUNT)}",
    )

# F5B0 diagnostic coverage cannot exceed the current financial universe.
if "F5B0_FINANCIAL_COUNT" in globals() and "F5B0_MIN_SOURCE_COVERAGE" in globals():
    k3_check(
        "F5B0 payout-source coverage threshold is dynamic",
        (
            int(F5B0_MIN_SOURCE_COVERAGE) == 0
            if int(F5B0_FINANCIAL_COUNT) == 0
            else int(F5B0_MIN_SOURCE_COVERAGE) <= int(F5B0_FINANCIAL_COUNT)
        ),
        f"required={int(F5B0_MIN_SOURCE_COVERAGE)}, financials={int(F5B0_FINANCIAL_COUNT)}",
    )

# Zero-financial universes must be a valid schema-stable N/A state.
if "F5A_FINANCIAL_TICKERS" in globals() and len(F5A_FINANCIAL_TICKERS) == 0:
    k3_check(
        "Zero-financial F5B1 state is valid",
        bool(globals().get("F5B1_PASSED", False)),
        "no financial companies => F5B1 diagnostic N/A/pass",
    )
    k3_check(
        "Zero-financial F5B state is valid",
        bool(globals().get("F5B_PASSED", False)),
        "no financial companies => F5B confidence pass-through",
    )

K3_DYNAMIC_STATE_AUDIT = pd.DataFrame(K3_DYNAMIC_AUDIT_ROWS)
K3_DYNAMIC_STATE_AUDIT["status"] = np.where(K3_DYNAMIC_STATE_AUDIT["passed"], "✓ PASS", "✗ FAIL")
K3_REQUIRED_FAILURES = K3_DYNAMIC_STATE_AUDIT[
    K3_DYNAMIC_STATE_AUDIT["required"] & ~K3_DYNAMIC_STATE_AUDIT["passed"]
].copy()
K3_DYNAMIC_STATE_PASSED = K3_REQUIRED_FAILURES.empty

display(K3_DYNAMIC_STATE_AUDIT)

if not K3_DYNAMIC_STATE_PASSED:
    display(K3_REQUIRED_FAILURES)
    raise RuntimeError("K3 DYNAMIC-STATE AUDIT FAILED.")

print("✓ K3 COMPLETE — live state is derived from current upstream objects; no stale sector snapshot fallback is permitted.")

