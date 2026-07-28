package com.overreality.vpn.data

import okhttp3.Interceptor
import okhttp3.Response
import java.io.IOException

class ResilientInterceptor : Interceptor {
    private val maxRetries = 3

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        var response: Response? = null
        var retries = 0

        while (true) {
            try {
                response = chain.proceed(request)
                
                val code = response.code
                if (code in 500..599) {
                    if (retries >= maxRetries) return response
                    response.close()
                    Thread.sleep((1000 * Math.pow(2.0, retries.toDouble())).toLong())
                    retries++
                    continue
                }
                
                if (code == 429) {
                    if (retries >= maxRetries) return response
                    val retryAfter = response.header("Retry-After")?.toLongOrNull() ?: 2L
                    response.close()
                    Thread.sleep(retryAfter * 1000)
                    retries++
                    continue
                }
                
                return response
            } catch (e: IOException) {
                if (retries >= 2) throw e // Timeout max 2 retries
                Thread.sleep(1000)
                retries++
            }
        }
    }
}
