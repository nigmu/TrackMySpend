package com.trackmyspend.companion

import android.app.Application
import com.google.android.material.color.DynamicColors

class CompanionApp : Application() {
    override fun onCreate() {
        super.onCreate()
        DynamicColors.applyToActivitiesIfAvailable(this)
    }
}
