// ============================================================
// iOS Platform Test Runner
// ============================================================

package com.videoqa

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import platform.Foundation.*

/**
 * iOS implementation of PlatformTestRunner.
 * Delegates tests to the orchestrator server since
 * Playwright is not available on iOS.
 */
actual class PlatformTestRunner {

    actual suspend fun runLocalTest(plan: TestPlan): TestResult {
        return withContext(Dispatchers.Default) {
            try {
                val urlString = "${getOrchestratorUrl()}/api/test"
                val url = NSURL(string = urlString)
                val request = NSMutableURLRequest(url)
                request.setHTTPMethod("POST")
                request.setValue("application/json", forHTTPHeaderField = "Content-Type")
                request.setValue("internal_testing", forHTTPHeaderField = "X-Traffic-Type")
                request.setValue(getApiKey(), forHTTPHeaderField = "X-API-Key")

                val json = buildJsonPayload(plan)
                request.setHTTPBody(json.encodeToByteArray())

                val (success, data) = executeRequest(request)

                if (success && data != null) {
                    TestResult(
                        id = "ios-${NSDate().timeIntervalSince1970.toLong()}",
                        name = plan.name,
                        status = "completed",
                        durationMs = 0,
                        actionsExecuted = 0,
                        errors = 0,
                        passed = true,
                        metrics = emptyMap(),
                        timestamp = NSDate().description
                    )
                } else {
                    TestResult(
                        id = "ios-${NSDate().timeIntervalSince1970.toLong()}",
                        name = plan.name,
                        status = "error",
                        durationMs = 0,
                        actionsExecuted = 0,
                        errors = 1,
                        passed = false,
                        metrics = emptyMap(),
                        timestamp = NSDate().description
                    )
                }
            } catch (e: Exception) {
                TestResult(
                    id = "ios-fallback-${NSDate().timeIntervalSince1970.toLong()}",
                    name = plan.name,
                    status = "error",
                    durationMs = 0,
                    actionsExecuted = 0,
                    errors = 1,
                    passed = false,
                    metrics = emptyMap(),
                    timestamp = NSDate().description
                )
            }
        }
    }

    actual fun getDeviceInfo(): Map<String, String> {
        return mapOf(
            "platform" to "ios",
            "device" to UIDevice.currentDevice.model,
            "os_version" to UIDevice.currentDevice.systemVersion,
            "traffic_type" to "internal_testing"
        )
    }

    private fun getOrchestratorUrl(): String {
        return NSProcessInfo.processInfo.environment["VIDEOQA_ORCHESTRATOR"] ?: "http://localhost:3000"
    }

    private fun getApiKey(): String {
        return NSProcessInfo.processInfo.environment["VIDEOQA_API_KEY"] ?: ""
    }

    private fun buildJsonPayload(plan: TestPlan): String {
        return """
            {
                "name": "${plan.name}",
                "videoUrl": "${plan.videoUrl}",
                "scenario": "${plan.scenario}",
                "concurrency": ${plan.concurrency},
                "durationSeconds": ${plan.durationSeconds}
            }
        """.trimIndent()
    }

    private fun executeRequest(request: NSMutableURLRequest): Pair<Boolean, ByteArray?> {
        var resultData: ByteArray? = null
        var success = false

        val semaphore = dispatch_semaphore_create(0)

        val task = NSURLSession.sharedSession.dataTaskWithRequest(request) { data, response, error ->
            if (error == null) {
                val httpResponse = response as? NSHTTPURLResponse
                if (httpResponse?.statusCode == 200) {
                    resultData = data?.toByteArray()
                    success = true
                }
            }
            dispatch_semaphore_signal(semaphore)
        }
        task.resume()
        dispatch_semaphore_wait(semaphore, DISPATCH_TIME_FOREVER)

        return Pair(success, resultData)
    }
}
