import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  attackMyAgent,
  getRuntimeStatus,
  resetRuntime,
  type AttackResponse,
  type RuntimeStatus,
} from "../lib/api";

import {
  buildConsoleModel,
} from "../lib/aegisData";

/* =========================================================
   HOOK
   ========================================================= */

export default function useAegisConsole() {
  const [
    result,
    setResult,
  ] = useState<AttackResponse | null>(
    null,
  );

  const [
    runtime,
    setRuntime,
  ] = useState<RuntimeStatus | null>(
    null,
  );

  const [
    attackLoading,
    setAttackLoading,
  ] = useState(false);

  const [
    runtimeLoading,
    setRuntimeLoading,
  ] = useState(false);

  const [
    resetLoading,
    setResetLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  /* =======================================================
     CONSOLE MODEL
     ======================================================= */

  const model = useMemo(
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
     LOAD RUNTIME STATUS
     ======================================================= */

  const refreshRuntime =
    useCallback(async () => {
      setRuntimeLoading(true);

      try {
        const status =
          await getRuntimeStatus();

        setRuntime(status);

        setError("");
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Runtime status unavailable.";

        setError(message);
      } finally {
        setRuntimeLoading(false);
      }
    }, []);

  /* =======================================================
     ATTACK MY AGENT
     ======================================================= */

  const executeAttack =
    useCallback(async () => {
      setAttackLoading(true);

      setError("");

      try {
        const response =
          await attackMyAgent();

        setResult(response);

        /*
         * The attack changes runtime receipts,
         * decisions and session budgets.
         * Refresh status immediately afterwards.
         */

        try {
          const status =
            await getRuntimeStatus();

          setRuntime(status);
        } catch {
          /*
           * Do not fail the successful attack
           * just because runtime refresh failed.
           */
        }

        return response;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Attack workflow failed.";

        setError(message);

        throw err;
      } finally {
        setAttackLoading(false);
      }
    }, []);

  /* =======================================================
     RESET RUNTIME
     ======================================================= */

  const executeReset =
    useCallback(async () => {
      setResetLoading(true);

      setError("");

      try {
        await resetRuntime();

        /*
         * Clear the previous attack result so
         * the UI returns to a clean state.
         */

        setResult(null);

        const status =
          await getRuntimeStatus();

        setRuntime(status);

        return status;
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Runtime reset failed.";

        setError(message);

        throw err;
      } finally {
        setResetLoading(false);
      }
    }, []);

  /* =======================================================
     INITIAL RUNTIME LOAD
     ======================================================= */

  useEffect(() => {
    void refreshRuntime();
  }, [
    refreshRuntime,
  ]);

  /* =======================================================
     MANUAL RESULT CONTROL

     Useful because Dashboard still controls
     the visual workflow stages.
     ======================================================= */

  const clearResult =
    useCallback(() => {
      setResult(null);
    }, []);

  const clearError =
    useCallback(() => {
      setError("");
    }, []);

  /* =======================================================
     RETURN
     ======================================================= */

  return {
    /* raw backend data */

    result,
    runtime,

    /* normalized data */

    model,

    /* loading states */

    attackLoading,
    runtimeLoading,
    resetLoading,

    /* error */

    error,

    /* actions */

    executeAttack,
    executeReset,
    refreshRuntime,
    clearResult,
    clearError,
  };
}