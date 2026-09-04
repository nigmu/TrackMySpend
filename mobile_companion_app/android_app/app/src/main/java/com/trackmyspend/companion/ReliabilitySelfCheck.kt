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

        val receivedAt = MessageStore.formatTime(1_725_500_000_000L)
        check(receivedAt.isNotBlank())
        check(
            MessageStore.decodeMessages(
                MessageStore.encodeMessages(
                    listOf(message.copy(receivedAt = receivedAt), message.copy(messageId = "dup", receivedAt = receivedAt)),
                ),
            ).size == 2,
        )
    }
}
