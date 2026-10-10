package com.trackmyspend.companion

object OtpFilter {

    const val OTP_CODE_LENGTH = 6
    const val IGNORED_BODY = "OTP ignored"

    private val code = Regex("(?<!\\d)\\d{$OTP_CODE_LENGTH}(?!\\d)")
    private val amountPrefix = Regex("(?i)(?:^|[^a-z])(?:rs|inr)\\.?\\s*$")

    fun isOtpSms(body: String): Boolean {
        if (!body.contains("OTP", ignoreCase = true)) return false
        return code.findAll(body).any { match ->
            !amountPrefix.containsMatchIn(body.substring(0, match.range.first))
        }
    }
}
