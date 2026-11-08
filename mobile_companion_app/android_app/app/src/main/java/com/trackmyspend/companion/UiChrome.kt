package com.trackmyspend.companion

import android.content.Context
import android.provider.Settings
import android.util.TypedValue
import android.view.MotionEvent
import android.view.View
import androidx.dynamicanimation.animation.SpringAnimation
import androidx.dynamicanimation.animation.SpringForce

object UiChrome {

    fun themeColor(context: Context, attr: Int): Int {
        val value = TypedValue()
        context.theme.resolveAttribute(attr, value, true)
        return if (value.resourceId != 0) {
            context.getColor(value.resourceId)
        } else {
            value.data
        }
    }

    fun reduceMotion(context: Context): Boolean {
        val cr = context.contentResolver
        val animator = Settings.Global.getFloat(cr, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        val transition = Settings.Global.getFloat(cr, Settings.Global.TRANSITION_ANIMATION_SCALE, 1f)
        return animator == 0f || transition == 0f
    }

    fun attachSpringPress(view: View) {
        if (reduceMotion(view.context)) return
        view.setOnTouchListener { v, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> springScale(v, 0.96f)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> springScale(v, 1f)
            }
            false
        }
    }

    fun springScale(view: View, value: Float) {
        if (reduceMotion(view.context)) {
            view.scaleX = value
            view.scaleY = value
            return
        }
        val force = SpringForce(value)
            .setDampingRatio(SpringForce.DAMPING_RATIO_MEDIUM_BOUNCY)
            .setStiffness(SpringForce.STIFFNESS_MEDIUM)
        SpringAnimation(view, SpringAnimation.SCALE_X).setSpring(force).start()
        SpringAnimation(view, SpringAnimation.SCALE_Y).setSpring(force).start()
    }
}
