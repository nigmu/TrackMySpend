package com.trackmyspend.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.PopupMenu
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import com.google.android.material.tabs.TabLayoutMediator
import com.trackmyspend.companion.databinding.ActivityMainBinding
import com.trackmyspend.companion.databinding.DialogUpdateManifestUrlBinding
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: PrefsStore
    private val executor = Executors.newSingleThreadExecutor()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val granted = SMS_PERMISSIONS.all { results[it] == true }
        if (!granted) {
            Snackbar.make(binding.root, R.string.permission_denied, Snackbar.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        prefs = PrefsStore(this)

        setSupportActionBar(binding.toolbar)
        binding.toolbar.setNavigationOnClickListener { showToolbarMenu() }

        val adapter = MainPagerAdapter(this)
        binding.viewPager.adapter = adapter
        TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, position ->
            tab.text = when (position) {
                0 -> getString(R.string.tab_filters)
                1 -> getString(R.string.tab_servers)
                else -> getString(R.string.tab_log)
            }
        }.attach()

        requestSmsPermissionsIfNeeded()
    }

    private fun showToolbarMenu() {
        PopupMenu(this, binding.toolbar).apply {
            menu.add(0, MENU_CHECK_UPDATES, 0, R.string.menu_check_updates)
            menu.add(0, MENU_UPDATE_MANIFEST_URL, 1, R.string.menu_update_manifest_url)
            setOnMenuItemClickListener { item ->
                when (item.itemId) {
                    MENU_CHECK_UPDATES -> {
                        checkForUpdates()
                        true
                    }
                    MENU_UPDATE_MANIFEST_URL -> {
                        showUpdateManifestUrlDialog()
                        true
                    }
                    else -> false
                }
            }
        }.show()
    }

    private fun showUpdateManifestUrlDialog() {
        val dialogBinding = DialogUpdateManifestUrlBinding.inflate(layoutInflater)
        prefs.getUpdateManifestUrl()?.let { dialogBinding.urlInput.setText(it) }
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.update_manifest_url_title)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.save) { _, _ ->
                val url = dialogBinding.urlInput.text?.toString().orEmpty()
                prefs.setUpdateManifestUrl(url)
                Snackbar.make(binding.root, R.string.update_manifest_url_saved, Snackbar.LENGTH_SHORT).show()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun checkForUpdates() {
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
        private const val MENU_CHECK_UPDATES = 1
        private const val MENU_UPDATE_MANIFEST_URL = 2

        private val SMS_PERMISSIONS = arrayOf(
            Manifest.permission.RECEIVE_SMS,
            Manifest.permission.READ_SMS,
        )
    }
}
