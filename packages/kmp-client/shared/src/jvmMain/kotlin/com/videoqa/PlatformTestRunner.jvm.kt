// ============================================================
// Desktop (JVM) Platform Test Runner
// ============================================================

package com.videoqa

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Desktop JVM implementation of PlatformTestRunner.
 * Can trigger local Playwright tests or delegate to orchestrator.
 */
actual class PlatformTestRunner {

    /**
     * Desktop can trigger tests via the orchestrator API
     * or launch a local Node.js process for Playwright tests.
     */
    actual suspend fun runLocalTest(plan: TestPlan): TestResult {
        return withContext(Dispatchers.IO) {
            try {
                val orchestratorUrl = System.getenv("VIDEOQA_ORCHESTRATOR") ?: "http://localhost:3000"
                val apiKey = System.getenv("VIDEOQA_API_KEY") ?: ""

                val url = URL("$orchestratorUrl/api/test")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setRequestProperty("X-API-Key", apiKey)
                connection.setRequestProperty("X-Traffic-Type", "internal_testing")
                connection.doOutput = true

                val json = """
                    {
                        "name": "${plan.name}",
                        "videoUrl": "${plan.videoUrl}",
                        "scenario": "${plan.scenario}",
                        "concurrency": ${plan.concurrency},
                        "durationSeconds": ${plan.durationSeconds}
                    }
                """.trimIndent()

                connection.outputStream.write(json.toByteArray())

                val responseCode = connection.responseCode
                if (responseCode == 200) {
                    val response = connection.inputStream.readBytes().toString(Charsets.UTF_8)
                    TestResult(
                        id = "desktop-${System.currentTimeMillis()}",
                        name = plan.name,
                        status = "completed",
                        durationMs = 0,
                        actionsExecuted = 0,
                        errors = 0,
                        passed = true,
                        metrics = emptyMap(),
                        timestamp = System.currentTimeMillis().toString()
                    )
                } else {
                    TestResult(
                        id = "desktop-${System.currentTimeMillis()}",
                        name = plan.name,
                        status = "error",
                        durationMs = 0,
                        actionsExecuted = 0,
                        errors = 1,
                        passed = false,
                        metrics = emptyMap(),
                        timestamp = System.currentTimeMillis().toString()
                    )
                }
            } catch (e: Exception) {
                TestResult(
                    id = "desktop-${System.currentTimeMillis()}",
                    name = plan.name,
                    status = "error",
                    durationMs = 0,
                    actionsExecuted = 0,
                    errors = 1,
                    passed = false,
                    metrics = emptyMap(),
                    timestamp = System.currentTimeMillis().toString()
                )
            }
        }
    }

    actual fun getDeviceInfo(): Map<String, String> {
        return mapOf(
            "platform" to "desktop",
            "os_name" to System.getProperty("os.name"),
            "os_version" to System.getProperty("os.version"),
            "java_version" to System.getProperty("java.version"),
            "traffic_type" to "internal_testing"
        )
    }
}
