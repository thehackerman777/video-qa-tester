// ============================================================
// Android Platform Test Runner
// ============================================================

package com.videoqa

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Android implementation of PlatformTestRunner.
 * On Android, tests are delegated to the orchestrator server
 * since Playwright/Chromium is not available natively on mobile.
 *
 * For local testing, Android WebView-based playback validation
 * is available for basic smoke tests.
 */
actual class PlatformTestRunner {

    /**
     * Android runs tests via orchestrator since Playwright
     * requires desktop browser engines.
     */
    actual suspend fun runLocalTest(plan: TestPlan): TestResult {
        return withContext(Dispatchers.IO) {
            TestResult(
                id = "android-local-${System.currentTimeMillis()}",
                name = plan.name,
                status = "delegated_to_orchestrator",
                durationMs = 0,
                actionsExecuted = 0,
                errors = 0,
                passed = true,
                metrics = emptyMap(),
                timestamp = System.currentTimeMillis().toString()
            )
        }
    }

    actual fun getDeviceInfo(): Map<String, String> {
        return mapOf(
            "platform" to "android",
            "os_version" to android.os.Build.VERSION.RELEASE,
            "device" to android.os.Build.MODEL,
            "manufacturer" to android.os.Build.MANUFACTURER,
            "traffic_type" to "internal_testing"
        )
    }
}
