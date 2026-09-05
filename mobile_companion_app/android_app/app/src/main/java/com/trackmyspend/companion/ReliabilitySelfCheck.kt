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
    }
}
