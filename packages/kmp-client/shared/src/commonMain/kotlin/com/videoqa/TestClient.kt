// ============================================================
// Video QA Tester — KMP Client
// ============================================================
// Shared Kotlin Multiplatform client for invoking tests
// from Android, iOS, and Desktop applications.

package com.videoqa

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*

/**
 * Client configuration for connecting to the Video QA orchestrator.
 */
@Serializable
data class QaClientConfig(
    val orchestratorUrl: String = "http://localhost:3000",
    val apiKey: String = "",
    val environment: String = "qa"
)

/**
 * A test plan to be executed.
 */
@Serializable
data class TestPlan(
    val name: String,
    val videoUrl: String,
    val scenario: String = "basic",
    val concurrency: Int = 1,
    val durationSeconds: Int = 60,
    val rampUpSeconds: Int = 10,
    val runOnDevice: Boolean = false
)

/**
 * Result of a completed test execution.
 */
@Serializable
data class TestResult(
    val id: String,
    val name: String,
    val status: String,
    val durationMs: Long,
    val actionsExecuted: Int,
    val errors: Int,
    val passed: Boolean,
    val metrics: Map<String, Double> = emptyMap(),
    val timestamp: String
)

/**
 * Summary of a test run.
 */
@Serializable
data class TestRunSummary(
    val totalTests: Int,
    val passed: Int,
    val failed: Int,
    val errored: Int,
    val totalDurationMs: Long,
    val successRate: Double
)

/**
 * Main KMP client for invoking tests from any platform.
 *
 * Usage:
 *   val client = VideoQAClient("http://orchestrator:3000", "my-api-key")
 *   val result = client.runTest(TestPlan(...))
 */
class VideoQAClient(
    private val config: QaClientConfig = QaClientConfig()
) {
    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        isLenient = true
    }

    private val httpClient = HttpClient {
        install(ContentNegotiation) {
            json(json)
        }
        defaultRequest {
            url(config.orchestratorUrl)
            header("X-API-Key", config.apiKey)
            header("X-Traffic-Type", "internal_testing")
            header("Content-Type", "application/json")
        }
    }

    /**
     * Run a single test against a video URL.
     * If runOnDevice is true, returns test parameters for local execution.
     */
    suspend fun runTest(plan: TestPlan): Result<TestResult> {
        return try {
            val response = httpClient.post("/api/test") {
                setBody(plan)
            }

            when (response.status) {
                HttpStatusCode.OK, HttpStatusCode.Created -> {
                    val result = response.body<TestResult>()
                    Result.success(result)
                }
                HttpStatusCode.Unauthorized -> {
                    Result.failure(Exception("Unauthorized: Check your API key"))
                }
                HttpStatusCode.TooManyRequests -> {
                    Result.failure(Exception("Rate limited by orchestrator"))
                }
                else -> {
                    val errorBody = try { response.body<String>() } catch (_: Exception) { response.status.description }
                    Result.failure(Exception("HTTP ${response.status}: $errorBody"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Run a load test through the orchestrator.
     */
    suspend fun runLoadTest(
        videoUrl: String,
        users: Int = 100,
        durationSeconds: Int = 120,
        scenario: String = "basic"
    ): Result<TestRunSummary> {
        return try {
            val response = httpClient.post("/api/loadtest") {
                setBody(mapOf(
                    "videoUrl" to videoUrl,
                    "users" to users,
                    "durationSeconds" to durationSeconds,
                    "scenario" to scenario
                ))
            }

            when (response.status) {
                HttpStatusCode.OK -> Result.success(response.body())
                else -> Result.failure(Exception("HTTP ${response.status}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Scan a YouTube channel and test all videos.
     */
    suspend fun scanChannel(
        channelId: String,
        maxVideos: Int = 10,
        scenario: String = "basic",
        apiKey: String? = null
    ): Result<TestRunSummary> {
        return try {
            val response = httpClient.post("/api/scan") {
                setBody(mapOf(
                    "channelId" to channelId,
                    "maxVideos" to maxVideos,
                    "scenario" to scenario,
                    "apiKey" to (apiKey ?: "")
                ))
            }

            when (response.status) {
                HttpStatusCode.OK -> Result.success(response.body())
                else -> Result.failure(Exception("HTTP ${response.status}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Get the orchestrator health status.
     */
    suspend fun healthCheck(): Result<Boolean> {
        return try {
            val response = httpClient.get("/health")
            Result.success(response.status == HttpStatusCode.OK)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Close the HTTP client. Call when done.
     */
    fun close() {
        httpClient.close()
    }
}

/**
 * Platform-specific test runner interface.
 * Each platform (Android, Desktop, iOS) implements this.
 */
expect class PlatformTestRunner {
    /**
     * Run a browser-based test locally on this device.
     * Note: Requires Playwright-compatible browser runtime.
     */
    suspend fun runLocalTest(plan: TestPlan): TestResult

    /**
     * Get device info for test metadata.
     */
    fun getDeviceInfo(): Map<String, String>
}
