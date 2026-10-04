import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  attackMyAgent,
  clearApiKey,
  getApiKey,
  getCapabilities,
  getHealth,
  getPersistenceStatus,
  getPolicy,
  getRuntimeStatus,
  getTelemetry,
  resetRuntime,
  setApiKey,
  type ApiRole,
  type AttackResponse,
  type CapabilitiesResponse,
  type HealthResponse,
  type PersistenceStatus,
  type PolicyResponse,
  type RuntimeStatus,
  type TelemetryResponse,
} from "../lib/api";

import {
  buildConsoleModel,
} from "../lib/aegisData";

/* =========================================================
   TYPES
   ========================================================= */

interface ApiAccessState {
  viewer: boolean;
  security: boolean;
  admin: boolean;
}

/* =========================================================
   HOOK
   ========================================================= */

export default function useAegisConsole() {
  /* =======================================================
     ATTACK RESULT
     ======================================================= */

  const [
    result,
    setResult,
  ] = useState<AttackResponse | null>(
    null,
  );

  /* =======================================================
     PUBLIC BACKEND DATA
     ======================================================= */

  const [
    health,
    setHealth,
  ] = useState<HealthResponse | null>(
    null,
  );

  const [
    policy,
    setPolicy,
  ] = useState<PolicyResponse | null>(
    null,
  );

  const [
    capabilities,
    setCapabilities,
  ] = useState<CapabilitiesResponse | null>(
    null,
  );

  /* =======================================================
     VIEWER DATA
     ======================================================= */

  const [
    runtime,
    setRuntime,
  ] = useState<RuntimeStatus | null>(
    null,
  );

  const [
    telemetry,
    setTelemetry,
  ] = useState<TelemetryResponse | null>(
    null,
  );

  const [
    persistence,
    setPersistence,
  ] = useState<PersistenceStatus | null>(
    null,
  );

  /* =======================================================
     API ACCESS STATE
     ======================================================= */

  const [
    apiAccess,
    setApiAccess,
  ] = useState<ApiAccessState>(
    () => ({
      viewer:
        Boolean(
          getApiKey(
            "viewer",
          ),
        ),

      security:
        Boolean(
          getApiKey(
            "security",
          ),
        ),

      admin:
        Boolean(
          getApiKey(
            "admin",
          ),
        ),
    }),
  );

  /* =======================================================
     LOADING STATES
     ======================================================= */

  const [
    attackLoading,
    setAttackLoading,
  ] = useState(false);

  const [
    runtimeLoading,
    setRuntimeLoading,
  ] = useState(false);

  const [
    telemetryLoading,
    setTelemetryLoading,
  ] = useState(false);

  const [
    publicLoading,
    setPublicLoading,
  ] = useState(false);

  const [
    resetLoading,
    setResetLoading,
  ] = useState(false);

  /* =======================================================
     ERROR
     ======================================================= */

  const [
    error,
    setError,
  ] = useState("");

  /* =======================================================
     NORMALIZED CONSOLE MODEL

     Keep the existing adapter exactly as before so
     Overview, Twin, Attacks, Guardrails, Replay and
     Reports continue working.
     ======================================================= */

  const model =
    useMemo(
      () =>
        buildConsoleModel(
          result,
          runtime,
        ),
      [
        result,
        runtime,
      ],
    );

  /* =======================================================
     UPDATE API ACCESS STATE
     ======================================================= */

  const refreshApiAccess =
    useCallback(() => {
      setApiAccess({
        viewer:
          Boolean(
            getApiKey(
              "viewer",
            ),
          ),

        security:
          Boolean(
            getApiKey(
              "security",
            ),
          ),

        admin:
          Boolean(
            getApiKey(
              "admin",
            ),
          ),
      });
    }, []);

  /* =======================================================
     CONFIGURE API KEY

     Keys are saved only to sessionStorage through api.ts.
     They are not hard-coded in React source.
     ======================================================= */

  const configureApiKey =
    useCallback(
      (
        role: ApiRole,
        key: string,
      ) => {
        setApiKey(
          role,
          key,
        );

        refreshApiAccess();
      },
      [
        refreshApiAccess,
      ],
    );

  /* =======================================================
     REMOVE API KEY
     ======================================================= */

  const removeApiKey =
    useCallback(
      (
        role?: ApiRole,
      ) => {
        clearApiKey(
          role,
        );

        refreshApiAccess();

        if (
          !role ||
          role === "viewer"
        ) {
          setRuntime(
            null,
          );

          setTelemetry(
            null,
          );

          setPersistence(
            null,
          );
        }
      },
      [
        refreshApiAccess,
      ],
    );

  /* =======================================================
     PUBLIC BACKEND DATA

     /health
     /policy
     /capabilities

     These do not require an API key.
     ======================================================= */

  const refreshPublicData =
    useCallback(async () => {
      setPublicLoading(
        true,
      );

      try {
        const [
          healthResult,
          policyResult,
          capabilitiesResult,
        ] =
          await Promise.allSettled(
            [
              getHealth(),
              getPolicy(),
              getCapabilities(),
            ],
          );

        if (
          healthResult.status ===
          "fulfilled"
        ) {
          setHealth(
            healthResult.value,
          );
        } else {
          setHealth(
            null,
          );
        }

        if (
          policyResult.status ===
          "fulfilled"
        ) {
          setPolicy(
            policyResult.value,
          );
        } else {
          setPolicy(
            null,
          );
        }

        if (
          capabilitiesResult.status ===
          "fulfilled"
        ) {
          setCapabilities(
            capabilitiesResult.value,
          );
        } else {
          setCapabilities(
            null,
          );
        }

        /*
         * Only surface an error when the actual health
         * endpoint fails. Policy/capabilities failing
         * should not make the whole console unusable.
         */

        if (
          healthResult.status ===
          "rejected"
        ) {
          const reason =
            healthResult.reason;

          setError(
            reason instanceof
              Error
              ? reason.message
              : "AegisTwin backend unavailable.",
          );
        }
      } finally {
        setPublicLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     RUNTIME STATUS

     VIEWER authentication required.
     ======================================================= */

  const refreshRuntime =
    useCallback(async () => {
      /*
       * Do not continuously generate 401 errors before
       * a viewer key has been configured.
       */

      if (
        !getApiKey(
          "viewer",
        )
      ) {
        setRuntime(
          null,
        );

        return null;
      }

      setRuntimeLoading(
        true,
      );

      try {
        const status =
          await getRuntimeStatus();

        setRuntime(
          status,
        );

        setError("");

        return status;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Runtime status unavailable.";

        setError(
          message,
        );

        throw err;
      } finally {
        setRuntimeLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     TELEMETRY

     VIEWER authentication required.
     ======================================================= */

  const refreshTelemetry =
    useCallback(async () => {
      if (
        !getApiKey(
          "viewer",
        )
      ) {
        setTelemetry(
          null,
        );

        return null;
      }

      setTelemetryLoading(
        true,
      );

      try {
        const response =
          await getTelemetry();

        setTelemetry(
          response,
        );

        setError("");

        return response;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Telemetry unavailable.";

        setError(
          message,
        );

        throw err;
      } finally {
        setTelemetryLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     PERSISTENCE STATUS

     VIEWER authentication required.
     ======================================================= */

  const refreshPersistence =
    useCallback(async () => {
      if (
        !getApiKey(
          "viewer",
        )
      ) {
        setPersistence(
          null,
        );

        return null;
      }

      try {
        const response =
          await getPersistenceStatus();

        setPersistence(
          response,
        );

        return response;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Persistence status unavailable.";

        setError(
          message,
        );

        throw err;
      }
    }, []);

  /* =======================================================
     REFRESH VIEWER / MANAGEMENT DATA

     One function for Dashboard refreshes.
     ======================================================= */

  const refreshManagementData =
    useCallback(async () => {
      if (
        !getApiKey(
          "viewer",
        )
      ) {
        setRuntime(
          null,
        );

        setTelemetry(
          null,
        );

        setPersistence(
          null,
        );

        return;
      }

      setRuntimeLoading(
        true,
      );

      setTelemetryLoading(
        true,
      );

      try {
        const [
          runtimeResult,
          telemetryResult,
          persistenceResult,
        ] =
          await Promise.allSettled(
            [
              getRuntimeStatus(),
              getTelemetry(),
              getPersistenceStatus(),
            ],
          );

        if (
          runtimeResult.status ===
          "fulfilled"
        ) {
          setRuntime(
            runtimeResult.value,
          );
        }

        if (
          telemetryResult.status ===
          "fulfilled"
        ) {
          setTelemetry(
            telemetryResult.value,
          );
        }

        if (
          persistenceResult.status ===
          "fulfilled"
        ) {
          setPersistence(
            persistenceResult.value,
          );
        }

        /*
         * Surface the first management API error,
         * typically 401/403 if the viewer key is wrong.
         */

        const failure =
          [
            runtimeResult,
            telemetryResult,
            persistenceResult,
          ].find(
            (item) =>
              item.status ===
              "rejected",
          );

        if (
          failure &&
          failure.status ===
            "rejected"
        ) {
          const reason =
            failure.reason;

          setError(
            reason instanceof
              Error
              ? reason.message
              : "Management API unavailable.",
          );
        } else {
          setError("");
        }
      } finally {
        setRuntimeLoading(
          false,
        );

        setTelemetryLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     CONNECT VIEWER KEY

     This will be used by the Dashboard authentication
     control we add next.
     ======================================================= */

  const connectViewer =
    useCallback(
      async (
        key: string,
      ) => {
        configureApiKey(
          "viewer",
          key,
        );

        /*
         * setApiKey writes synchronously to sessionStorage,
         * so protected calls can be made immediately.
         */

        await refreshManagementData();
      },
      [
        configureApiKey,
        refreshManagementData,
      ],
    );

  /* =======================================================
     CONNECT SECURITY KEY
     ======================================================= */

  const connectSecurity =
    useCallback(
      (
        key: string,
      ) => {
        configureApiKey(
          "security",
          key,
        );
      },
      [
        configureApiKey,
      ],
    );

  /* =======================================================
     CONNECT ADMIN KEY
     ======================================================= */

  const connectAdmin =
    useCallback(
      (
        key: string,
      ) => {
        configureApiKey(
          "admin",
          key,
        );
      },
      [
        configureApiKey,
      ],
    );

  /* =======================================================
     ATTACK MY AGENT

     Public endpoint.
     ======================================================= */

  const executeAttack =
    useCallback(async () => {
      setAttackLoading(
        true,
      );

      setError("");

      try {
        const response =
          await attackMyAgent();

        setResult(
          response,
        );

        /*
         * The attack changes decisions, receipts,
         * telemetry and session budget state.
         *
         * Refresh management data if a viewer
         * credential has been configured.
         */

        if (
          getApiKey(
            "viewer",
          )
        ) {
          try {
            const [
              status,
              telemetryResponse,
              persistenceResponse,
            ] =
              await Promise.all(
                [
                  getRuntimeStatus(),
                  getTelemetry(),
                  getPersistenceStatus(),
                ],
              );

            setRuntime(
              status,
            );

            setTelemetry(
              telemetryResponse,
            );

            setPersistence(
              persistenceResponse,
            );
          } catch {
            /*
             * Attack My Agent itself succeeded.
             * Do not invalidate the attack just because
             * a secondary management refresh failed.
             */
          }
        }

        return response;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Attack workflow failed.";

        setError(
          message,
        );

        throw err;
      } finally {
        setAttackLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     RESET RUNTIME

     ADMIN authentication required.
     ======================================================= */

  const executeReset =
    useCallback(async () => {
      setResetLoading(
        true,
      );

      setError("");

      try {
        /*
         * Never pretend this is a normal viewer action.
         */

        if (
          !getApiKey(
            "admin",
          )
        ) {
          throw new Error(
            "Admin API key required to reset the AegisTwin runtime.",
          );
        }

        await resetRuntime();

        /*
         * Clear current attack evidence from the UI.
         */

        setResult(
          null,
        );

        /*
         * If a viewer credential exists, fetch the newly
         * reset runtime/telemetry/persistence state.
         */

        if (
          getApiKey(
            "viewer",
          )
        ) {
          const [
            runtimeResult,
            telemetryResult,
            persistenceResult,
          ] =
            await Promise.allSettled(
              [
                getRuntimeStatus(),
                getTelemetry(),
                getPersistenceStatus(),
              ],
            );

          if (
            runtimeResult.status ===
            "fulfilled"
          ) {
            setRuntime(
              runtimeResult.value,
            );
          }

          if (
            telemetryResult.status ===
            "fulfilled"
          ) {
            setTelemetry(
              telemetryResult.value,
            );
          }

          if (
            persistenceResult.status ===
            "fulfilled"
          ) {
            setPersistence(
              persistenceResult.value,
            );
          }
        } else {
          setRuntime(
            null,
          );

          setTelemetry(
            null,
          );

          setPersistence(
            null,
          );
        }

        return true;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Runtime reset failed.";

        setError(
          message,
        );

        throw err;
      } finally {
        setResetLoading(
          false,
        );
      }
    }, []);

  /* =======================================================
     INITIAL LOAD
     ======================================================= */

  useEffect(() => {
    /*
     * Public backend information is always safe to load.
     */

    void refreshPublicData();

    /*
     * Only request VIEWER endpoints if a viewer key
     * has already been configured in this browser session.
     */

    if (
      getApiKey(
        "viewer",
      )
    ) {
      void refreshManagementData();
    }
  }, [
    refreshPublicData,
    refreshManagementData,
  ]);

  /* =======================================================
     MANUAL RESULT CONTROL
     ======================================================= */

  const clearResult =
    useCallback(() => {
      setResult(
        null,
      );
    }, []);

  const clearError =
    useCallback(() => {
      setError("");
    }, []);

  /* =======================================================
     RETURN
     ======================================================= */

  return {
    /* -----------------------------------------------------
       ATTACK / TWIN
       ----------------------------------------------------- */

    result,

    /* -----------------------------------------------------
       PUBLIC BACKEND
       ----------------------------------------------------- */

    health,
    policy,
    capabilities,

    /* -----------------------------------------------------
       MANAGEMENT BACKEND
       ----------------------------------------------------- */

    runtime,
    telemetry,
    persistence,

    /* -----------------------------------------------------
       NORMALIZED EXISTING MODEL
       ----------------------------------------------------- */

    model,

    /* -----------------------------------------------------
       AUTH / RBAC STATE
       ----------------------------------------------------- */

    apiAccess,

    /* -----------------------------------------------------
       LOADING
       ----------------------------------------------------- */

    attackLoading,
    runtimeLoading,
    telemetryLoading,
    publicLoading,
    resetLoading,

    /* -----------------------------------------------------
       ERROR
       ----------------------------------------------------- */

    error,

    /* -----------------------------------------------------
       CORE ACTIONS
       ----------------------------------------------------- */

    executeAttack,
    executeReset,

    /* -----------------------------------------------------
       REFRESH ACTIONS
       ----------------------------------------------------- */

    refreshRuntime,
    refreshTelemetry,
    refreshPersistence,
    refreshManagementData,
    refreshPublicData,

    /* -----------------------------------------------------
       RBAC ACTIONS
       ----------------------------------------------------- */

    configureApiKey,
    removeApiKey,

    connectViewer,
    connectSecurity,
    connectAdmin,

    /* -----------------------------------------------------
       UI CONTROL
       ----------------------------------------------------- */

    clearResult,
    clearError,
  };
}