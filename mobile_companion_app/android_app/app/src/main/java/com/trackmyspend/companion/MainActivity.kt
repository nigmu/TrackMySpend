package com.trackmyspend.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentManager
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import com.trackmyspend.companion.databinding.ActivityMainBinding
import com.trackmyspend.companion.databinding.DialogBackfillSettingsBinding
import com.trackmyspend.companion.databinding.DialogUpdateManifestUrlBinding
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: PrefsStore
    private val executor = Executors.newSingleThreadExecutor()
    private val backfillRunning = AtomicBoolean(false)
    private var selectedTag = TAG_HOME
    private var navReady = false

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        recoverMissedSms()
    }

    private val storagePermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) exportOutbox() else {
            Snackbar.make(binding.root, R.string.storage_permission_needed, Snackbar.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        prefs = PrefsStore(this)
        if (BuildConfig.DEBUG) ReliabilitySelfCheck.run()

        setSupportActionBar(binding.toolbar)
        binding.toolbar.setNavigationOnClickListener {
            if (isSettingsVisible()) supportFragmentManager.popBackStack()
        }

        binding.bottomNav.setOnItemSelectedListener { item ->
            if (!navReady) return@setOnItemSelectedListener true
            val tag = when (item.itemId) {
                R.id.nav_home -> TAG_HOME
                R.id.nav_servers -> TAG_SERVERS
                R.id.nav_filters -> TAG_FILTERS
                else -> TAG_LOG
            }
            showTab(tag)
            true
        }

        supportFragmentManager.addOnBackStackChangedListener { updateChrome() }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (isSettingsVisible()) {
                    supportFragmentManager.popBackStack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    isEnabled = true
                }
            }
        })

        selectedTag = savedInstanceState?.getString(STATE_TAB) ?: TAG_HOME
        if (savedInstanceState == null) {
            showTab(selectedTag)
        } else {
            updateChrome()
        }
        val navId = when (selectedTag) {
            TAG_SERVERS -> R.id.nav_servers
            TAG_FILTERS -> R.id.nav_filters
            TAG_LOG -> R.id.nav_log
            else -> R.id.nav_home
        }
        binding.bottomNav.selectedItemId = navId
        navReady = true

        binding.root.post { applyBlur() }
        requestSmsPermissionsIfNeeded()
        recoverMissedSms()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(STATE_TAB, selectedTag)
    }

    override fun onCreateOptionsMenu(menu: android.view.Menu): Boolean {
        if (selectedTag == TAG_HOME && !isSettingsVisible()) {
            menuInflater.inflate(R.menu.menu_home, menu)
        }
        return true
    }

    override fun onOptionsItemSelected(item: android.view.MenuItem): Boolean {
        if (item.itemId == R.id.action_settings) {
            openSettings()
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    fun startBackfill(source: BackfillSource) {
        if (!hasSmsPermissions()) {
            Snackbar.make(binding.root, R.string.backfill_no_permission, Snackbar.LENGTH_LONG).show()
            return
        }
        if (!backfillRunning.compareAndSet(false, true)) return
        setBackfillLoading(true)
        executor.execute {
            val result = InboxBackfill.run(this, source)
            runOnUiThread {
                backfillRunning.set(false)
                setBackfillLoading(false)
                showBackfillResult(result)
            }
        }
    }

    fun requestSmsPermissions() = requestSmsPermissionsIfNeeded()

    fun hasSmsPermissions(): Boolean = SMS_PERMISSIONS.all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    fun openSettings() {
        if (isSettingsVisible()) return
        val settings = SettingsFragment()
        supportFragmentManager.beginTransaction()
            .add(R.id.fragmentContainer, settings, TAG_SETTINGS)
            .addToBackStack(TAG_SETTINGS)
            .commit()
    }

    fun showBackfillSettingsSheet() {
        val dialogBinding = DialogBackfillSettingsBinding.inflate(layoutInflater)
        dialogBinding.lookbackInput.setText(prefs.getBackfillLookbackHours().toString())
        dialogBinding.maxRowsInput.setText(prefs.getBackfillMaxRows().toString())
        val dialog = BottomSheetDialog(this, R.style.ThemeOverlay_TMS_BottomSheet)
        dialog.setContentView(dialogBinding.root)
        dialogBinding.cancelButton.setOnClickListener { dialog.dismiss() }
        dialogBinding.saveButton.setOnClickListener {
            val hours = dialogBinding.lookbackInput.text?.toString()?.toIntOrNull()
            val rows = dialogBinding.maxRowsInput.text?.toString()?.toIntOrNull()
            if (hours == null || rows == null) {
                Snackbar.make(binding.root, R.string.backfill_settings_invalid, Snackbar.LENGTH_LONG).show()
                return@setOnClickListener
            }
            prefs.setBackfillLookbackHours(hours)
            prefs.setBackfillMaxRows(rows)
            dialog.dismiss()
            Snackbar.make(binding.root, R.string.backfill_settings_saved, Snackbar.LENGTH_SHORT).show()
            (supportFragmentManager.findFragmentByTag(TAG_SETTINGS) as? SettingsFragment)?.onResume()
        }
        dialog.show()
    }

    fun showUpdateManifestUrlSheet() {
        val dialogBinding = DialogUpdateManifestUrlBinding.inflate(layoutInflater)
        prefs.getUpdateManifestUrl()?.let { dialogBinding.urlInput.setText(it) }
        val dialog = BottomSheetDialog(this, R.style.ThemeOverlay_TMS_BottomSheet)
        dialog.setContentView(dialogBinding.root)
        dialogBinding.cancelButton.setOnClickListener { dialog.dismiss() }
        dialogBinding.saveButton.setOnClickListener {
            val url = dialogBinding.urlInput.text?.toString().orEmpty()
            prefs.setUpdateManifestUrl(url)
            dialog.dismiss()
            Snackbar.make(binding.root, R.string.update_manifest_url_saved, Snackbar.LENGTH_SHORT).show()
            (supportFragmentManager.findFragmentByTag(TAG_SETTINGS) as? SettingsFragment)?.onResume()
        }
        dialog.show()
    }

    fun requestExportOutbox() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            exportOutbox()
            return
        }
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.WRITE_EXTERNAL_STORAGE,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) {
            exportOutbox()
        } else {
            storagePermissionLauncher.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
    }

    fun checkForUpdates() {
        val manifestUrl = prefs.getUpdateManifestUrl()
        if (manifestUrl.isNullOrBlank()) {
            Snackbar.make(binding.root, R.string.update_manifest_url_not_set, Snackbar.LENGTH_LONG).show()
            return
        }
        Snackbar.make(binding.root, R.string.update_checking, Snackbar.LENGTH_SHORT).show()
        executor.execute {
            val result = runCatching {
                val manifest = UpdateChecker.fetchManifest(manifestUrl)
                val installedCode = UpdateChecker.getInstalledVersionCode(this)
                UpdateChecker.compare(installedCode, manifest)
            }.getOrElse { CompareResult.Error(it.message ?: it.javaClass.simpleName) }
            runOnUiThread { handleCompareResult(result) }
        }
    }

    private fun recoverMissedSms() {
        UploadWorker.enqueueAllPending(this)
        if (!hasSmsPermissions()) return
        if (MessageStore(this).isEmpty()) return
        startBackfill(BackfillSource.ON_OPEN)
    }

    private fun setBackfillLoading(loading: Boolean) {
        binding.backfillCard.visibility = if (loading) View.VISIBLE else View.GONE
        applyBlur(forceDisable = loading)
    }

    private fun applyBlur(forceDisable: Boolean = backfillRunning.get()) {
        val enable = !forceDisable && !UiChrome.reduceTransparency(this)
        UiChrome.setupBlur(binding.toolbarBlur, binding.blurTarget, this, enable)
        UiChrome.setupBlur(binding.navBlur, binding.blurTarget, this, enable)
        if (binding.backfillCard.visibility == View.VISIBLE) {
            UiChrome.setupBlur(binding.backfillCard, binding.blurTarget, this, enable && !forceDisable)
        }
    }

    private fun showBackfillResult(result: BackfillResult) {
        if (result.skipped) return
        val sourceLabel = when (result.source) {
            BackfillSource.AFTER_SERVER_SAVE -> "save"
            BackfillSource.ON_OPEN -> "open"
            BackfillSource.MANUAL -> "manual"
        }
        val text = when {
            result.error != null && result.watermarkUsed ->
                getString(R.string.backfill_watermark_failed)
            result.error != null ->
                result.error
            result.hitCap ->
                getString(R.string.backfill_done_cap, sourceLabel, result.enqueued)
            else ->
                getString(R.string.backfill_done, sourceLabel, result.enqueued)
        }
        Snackbar.make(binding.root, text, Snackbar.LENGTH_LONG).show()
    }

    private fun showTab(tag: String) {
        if (isSettingsVisible()) {
            supportFragmentManager.popBackStack(TAG_SETTINGS, FragmentManager.POP_BACK_STACK_INCLUSIVE)
        }
        selectedTag = tag
        val tx = supportFragmentManager.beginTransaction()
        TAB_TAGS.forEach { existing ->
            val fragment = supportFragmentManager.findFragmentByTag(existing)
            if (existing == tag) {
                if (fragment == null) {
                    tx.add(R.id.fragmentContainer, createTab(tag), tag)
                } else {
                    tx.show(fragment)
                }
            } else if (fragment != null) {
                tx.hide(fragment)
            }
        }
        tx.commit()
        updateChrome()
    }

    private fun createTab(tag: String): Fragment = when (tag) {
        TAG_HOME -> HomeFragment()
        TAG_SERVERS -> ServersFragment()
        TAG_FILTERS -> FiltersFragment()
        else -> LogFragment()
    }

    private fun isSettingsVisible(): Boolean =
        supportFragmentManager.findFragmentByTag(TAG_SETTINGS) != null

    private fun updateChrome() {
        val settings = isSettingsVisible()
        binding.navBlur.visibility = if (settings) View.GONE else View.VISIBLE
        binding.toolbar.title = when {
            settings -> getString(R.string.settings)
            selectedTag == TAG_SERVERS -> getString(R.string.tab_servers)
            selectedTag == TAG_FILTERS -> getString(R.string.tab_filters)
            selectedTag == TAG_LOG -> getString(R.string.tab_log)
            else -> getString(R.string.app_name)
        }
        if (settings) {
            binding.toolbar.setNavigationIcon(androidx.appcompat.R.drawable.abc_ic_ab_back_material)
            binding.toolbar.navigationContentDescription = getString(R.string.navigate_up)
        } else {
            binding.toolbar.navigationIcon = null
        }
        invalidateOptionsMenu()
    }

    private fun exportOutbox() {
        Snackbar.make(binding.root, R.string.export_started, Snackbar.LENGTH_SHORT).show()
        executor.execute {
            val result = runCatching { OutboxExporter.exportToDownloads(this) }
            runOnUiThread {
                result.fold(
                    onSuccess = { name ->
                        Snackbar.make(
                            binding.root,
                            getString(R.string.export_done, name),
                            Snackbar.LENGTH_LONG,
                        ).show()
                    },
                    onFailure = { error ->
                        Snackbar.make(
                            binding.root,
                            getString(R.string.export_failed, error.message ?: error.javaClass.simpleName),
                            Snackbar.LENGTH_LONG,
                        ).show()
                    },
                )
            }
        }
    }

    private fun handleCompareResult(result: CompareResult) {
        when (result) {
            is CompareResult.UpToDate -> {
                Snackbar.make(
                    binding.root,
                    getString(R.string.update_up_to_date, BuildConfig.VERSION_NAME),
                    Snackbar.LENGTH_LONG,
                ).show()
            }
            is CompareResult.Error -> {
                Snackbar.make(binding.root, result.message, Snackbar.LENGTH_LONG).show()
            }
            is CompareResult.UpdateAvailable -> showUpdateDialog(result)
        }
    }

    private fun showUpdateDialog(result: CompareResult.UpdateAvailable) {
        val manifest = result.manifest
        val installedCode = UpdateChecker.getInstalledVersionCode(this).toInt()
        val body = buildString {
            append(
                getString(
                    R.string.update_dialog_body,
                    BuildConfig.VERSION_NAME,
                    installedCode,
                    manifest.versionName,
                    manifest.versionCode,
                )
            )
            manifest.changelog?.let {
                append("\n\n")
                append(getString(R.string.update_changelog, it))
            }
            if (!result.isUpgrade) {
                append("\n\n")
                append(getString(R.string.update_downgrade_warning))
            }
        }
        val title = if (result.isUpgrade) R.string.update_available_title else R.string.update_downgrade_title
        val confirm = if (result.isUpgrade) R.string.update_confirm else R.string.update_confirm_downgrade
        MaterialAlertDialogBuilder(this)
            .setTitle(title)
            .setMessage(body)
            .setPositiveButton(confirm) { _, _ -> downloadAndInstall(manifest.apkUrl) }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun downloadAndInstall(apkUrl: String) {
        Snackbar.make(binding.root, R.string.update_downloading, Snackbar.LENGTH_SHORT).show()
        executor.execute {
            val downloadResult = runCatching {
                UpdateChecker.downloadApk(apkUrl, cacheDir)
            }
            runOnUiThread {
                downloadResult.fold(
                    onSuccess = { apkFile ->
                        runCatching { UpdateChecker.launchInstall(this, apkFile) }
                            .onFailure { e ->
                                Snackbar.make(
                                    binding.root,
                                    e.message ?: e.javaClass.simpleName,
                                    Snackbar.LENGTH_LONG,
                                ).show()
                            }
                    },
                    onFailure = { e ->
                        Snackbar.make(
                            binding.root,
                            e.message ?: e.javaClass.simpleName,
                            Snackbar.LENGTH_LONG,
                        ).show()
                    },
                )
            }
        }
    }

    private fun requestSmsPermissionsIfNeeded() {
        val missing = SMS_PERMISSIONS.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        }
    }

    companion object {
        const val TAG_HOME = "home"
        const val TAG_SERVERS = "servers"
        const val TAG_FILTERS = "filters"
        const val TAG_LOG = "log"
        const val TAG_SETTINGS = "settings"
        private const val STATE_TAB = "selected_tab"
        private val TAB_TAGS = listOf(TAG_HOME, TAG_SERVERS, TAG_FILTERS, TAG_LOG)

        private val SMS_PERMISSIONS = arrayOf(
            Manifest.permission.RECEIVE_SMS,
            Manifest.permission.READ_SMS,
        )
    }
}
