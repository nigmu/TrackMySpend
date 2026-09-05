package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.work.WorkManager
import com.google.android.material.snackbar.Snackbar
import com.trackmyspend.companion.databinding.FragmentHomeBinding

class HomeFragment : Fragment() {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!
    private lateinit var prefs: PrefsStore
    private lateinit var store: MessageStore
    private var healthStatus = HealthStatus.UNKNOWN

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        store = MessageStore(requireContext())
        UiChrome.attachSpringPress(binding.pullSmsButton)
        UiChrome.attachSpringPress(binding.checkUpdatesButton)
        UiChrome.attachSpringPress(binding.retryAllButton)
        binding.grantPermissionButton.setOnClickListener {
            host()?.requestSmsPermissions()
        }
        binding.pullSmsButton.setOnClickListener {
            host()?.startBackfill(BackfillSource.MANUAL)
        }
        binding.checkUpdatesButton.setOnClickListener { host()?.checkForUpdates() }
        binding.manageSettingsButton.setOnClickListener { host()?.openSettings() }
        binding.retryAllButton.setOnClickListener { retryAllFailed() }
        WorkManager.getInstance(requireContext())
            .getWorkInfosByTagLiveData(UploadWorker.TAG)
            .observe(viewLifecycleOwner) { refresh() }
        refresh()
        probePrimary()
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val host = host()
        binding.permissionCard.visibility =
            if (host?.hasSmsPermissions() == true) View.GONE else View.VISIBLE
        val entries = store.getAll()
        val pending = entries.count {
            it.status == DeliveryStatus.PENDING || it.status == DeliveryStatus.SENDING
        }
        val failed = entries.count { it.status == DeliveryStatus.FAILED }
        binding.pendingCountText.text = pending.toString()
        binding.failedCountText.text = failed.toString()
        binding.retryAllButton.visibility = if (failed > 0) View.VISIBLE else View.GONE
        val primary = prefs.getServers().firstOrNull()
        binding.primaryServerText.text = primary?.name ?: getString(R.string.home_no_server)
        if (primary == null) healthStatus = HealthStatus.UNKNOWN
        StatusPills.applyHealth(binding.serverStatusChip, healthStatus)
        val lastSent = entries.firstOrNull { it.status == DeliveryStatus.SENT }
        binding.lastUploadText.text = getString(
            R.string.home_last_upload,
        ) + " · " + (lastSent?.ackedAt ?: getString(R.string.home_last_upload_never))
    }

    private fun probePrimary() {
        val primary = prefs.getServers().firstOrNull() ?: return
        healthStatus = HealthStatus.CHECKING
        StatusPills.applyHealth(binding.serverStatusChip, healthStatus)
        Thread {
            val (ok, _) = SmsUploader.testHealth(primary.url)
            if (!isAdded) return@Thread
            requireActivity().runOnUiThread {
                if (!isAdded) return@runOnUiThread
                healthStatus = if (ok) HealthStatus.OK else HealthStatus.UNREACHABLE
                StatusPills.applyHealth(binding.serverStatusChip, healthStatus)
            }
        }.start()
    }

    private fun retryAllFailed() {
        val failed = store.getAll().filter { it.status == DeliveryStatus.FAILED }
        var queued = 0
        failed.forEach { if (UploadWorker.retry(requireContext(), it.messageId)) queued++ }
        if (queued > 0) {
            Snackbar.make(binding.root, R.string.retry_queued, Snackbar.LENGTH_SHORT).show()
            refresh()
        }
    }

    private fun host(): MainActivity? = activity as? MainActivity

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
