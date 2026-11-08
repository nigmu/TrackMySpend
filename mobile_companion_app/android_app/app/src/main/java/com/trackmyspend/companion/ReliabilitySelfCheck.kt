package com.trackmyspend.companion

object ReliabilitySelfCheck {

    fun run() {
        val servers = listOf(
            ServerConfig("primary", "Primary", "https://primary", priority = 1),
            ServerConfig("backup-1", "Backup 1", "https://backup-1", priority = 2),
            ServerConfig("backup-2", "Backup 2", "https://backup-2", priority = 3),
        )
        check(SmsUploader.attemptPlan(servers).map { it.id } == listOf(
            "primary",
            "primary",
            "primary",
            "backup-1",
            "backup-2",
        ))

        val message = OutboxMessage(
            messageId = "self-check",
            sender = "BANK",
            body = "Rs.100 spent",
            receivedAt = "2026-09-05T02:00:00+05:30",
            status = DeliveryStatus.FAILED,
            attemptCount = 5,
            lastError = "offline",
        )
        check(MessageStore.decodeMessages(MessageStore.encodeMessages(listOf(message))) == listOf(message))

        val receivedAtMillis = 1_725_500_000_000L
        val receivedAt = MessageStore.formatTime(receivedAtMillis)
        check(receivedAt.isNotBlank())
        check(MessageStore.parseTimeMillis(receivedAt) == receivedAtMillis)
        check(
            MessageStore.decodeMessages(
                MessageStore.encodeMessages(
                    listOf(message.copy(receivedAt = receivedAt), message.copy(messageId = "dup", receivedAt = receivedAt)),
                ),
            ).size == 2,
        )

        // Cursor: local max wins; empty outbox falls back to lookback window.
        val now = 1_800_000_000_000L
        val lookback = InboxBackfill.chooseLocalOrLookback(null, 48, now)
        check(lookback == now - 48L * 60L * 60L * 1000L)
        check(InboxBackfill.chooseLocalOrLookback(now - 5_000L, 48, now) == now - 5_000L)
        check(!InboxBackfill.shouldPostBackfill(0, null))
        check(InboxBackfill.shouldPostBackfill(1, null))
        check(InboxBackfill.shouldPostBackfill(0, "watermark"))
        check(InboxBackfill.backfillSeverity(null, false) == "info")
        check(InboxBackfill.backfillSeverity(null, true) == "warning")
        check(InboxBackfill.backfillSeverity("SMS permission not granted", false) == "warning")

        check(!OtpFilter.isOtpSms(
            "Spent Rs.61.71 On HDFC Bank Card 6517 At UBER INDIA SYSTEMS PRI On 2026-10-09:21:51:52." +
                "Not You? To Block+Reissue Call 18002586161/SMS BLOCK CC 6517 to 7308080808",
        ))
        check(OtpFilter.isOtpSms(
            "OTP is 492045 for txn of INR 61.71 at UBER INDIA  on HDFC Bank card ending 6517. " +
                "Valid till  09:54. Do not share OTP for security reasons",
        ))
        check(OtpFilter.isOtpSms("OTP is 026101 for txn of INR 242.72"))
        check(!OtpFilter.isOtpSms(
            "Rs.299 without OTP/PIN HDFC Bank Card x6517 At SPOTIFYINDIA On 2026-09-14:02:36:34." +
                "Not U? Block&Reissue:Call 18002586161/SMS BLOCK CC 6517 to 7308080808",
        ))
        check(!OtpFilter.isOtpSms("Rs.100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("Rs. 100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("Rs 100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("Rs100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("INR 100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("INR.100000 without OTP/PIN"))
        check(!OtpFilter.isOtpSms("INR100000 without OTP/PIN"))
        check(OtpFilter.isOtpSms("OTP is 492045 for txn of INR 100000"))

        val ignored = message.copy(
            messageId = "otp",
            body = OtpFilter.IGNORED_BODY,
            status = DeliveryStatus.IGNORED,
        )
        val decoded = MessageStore.decodeMessages(MessageStore.encodeMessages(listOf(ignored))).single()
        check(decoded.status == DeliveryStatus.IGNORED)
        check(decoded.body == OtpFilter.IGNORED_BODY)
    }
}
