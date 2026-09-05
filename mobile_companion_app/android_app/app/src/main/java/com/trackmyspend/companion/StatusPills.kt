package com.trackmyspend.companion

import com.google.android.material.chip.Chip
import com.google.android.material.R as MaterialR

enum class HealthStatus { UNKNOWN, CHECKING, OK, UNREACHABLE }

object StatusPills {

    fun applyHealth(chip: Chip, status: HealthStatus) {
        val ctx = chip.context
        val (label, container, onContainer) = when (status) {
            HealthStatus.OK -> Triple(
                R.string.status_ok,
                R.attr.colorSuccessContainer,
                R.attr.colorOnSuccessContainer,
            )
            HealthStatus.UNREACHABLE -> Triple(
                R.string.status_unreachable,
                MaterialR.attr.colorErrorContainer,
                MaterialR.attr.colorOnErrorContainer,
            )
            HealthStatus.CHECKING -> Triple(
                R.string.status_checking,
                R.attr.colorPendingContainer,
                R.attr.colorOnPendingContainer,
            )
            HealthStatus.UNKNOWN -> Triple(
                R.string.status_unknown,
                MaterialR.attr.colorSurfaceVariant,
                MaterialR.attr.colorOnSurfaceVariant,
            )
        }
        chip.text = ctx.getString(label)
        chip.chipBackgroundColor = android.content.res.ColorStateList.valueOf(UiChrome.themeColor(ctx, container))
        chip.setTextColor(UiChrome.themeColor(ctx, onContainer))
        chip.isClickable = false
        chip.isCheckable = false
    }

    fun applyDelivery(chip: Chip, status: DeliveryStatus) {
        val ctx = chip.context
        val (label, container, onContainer) = when (status) {
            DeliveryStatus.SENT -> Triple(
                R.string.status_sent,
                R.attr.colorSuccessContainer,
                R.attr.colorOnSuccessContainer,
            )
            DeliveryStatus.FAILED -> Triple(
                R.string.status_failed,
                MaterialR.attr.colorErrorContainer,
                MaterialR.attr.colorOnErrorContainer,
            )
            DeliveryStatus.SENDING, DeliveryStatus.PENDING -> Triple(
                if (status == DeliveryStatus.SENDING) R.string.status_sending else R.string.status_pending,
                R.attr.colorPendingContainer,
                R.attr.colorOnPendingContainer,
            )
        }
        chip.text = ctx.getString(label)
        chip.chipBackgroundColor = android.content.res.ColorStateList.valueOf(UiChrome.themeColor(ctx, container))
        chip.setTextColor(UiChrome.themeColor(ctx, onContainer))
        chip.isClickable = false
        chip.isCheckable = false
    }
}
