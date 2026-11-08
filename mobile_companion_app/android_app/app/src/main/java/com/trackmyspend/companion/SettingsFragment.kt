package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.trackmyspend.companion.databinding.FragmentSettingsBinding

class SettingsFragment : Fragment() {

    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.manifestRow.setOnClickListener { host()?.showUpdateManifestUrlSheet() }
        binding.backfillRow.setOnClickListener { host()?.showBackfillSettingsSheet() }
        binding.exportRow.setOnClickListener { host()?.requestExportOutbox() }
        binding.deleteOutboxRow.setOnClickListener { host()?.confirmDeleteOutbox() }
        refresh()
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val prefs = PrefsStore(requireContext())
        val manifest = prefs.getUpdateManifestUrl()
        binding.manifestSubtitle.text = manifest ?: getString(R.string.settings_manifest_subtitle)
        binding.backfillSubtitle.text = getString(
            R.string.settings_backfill_subtitle,
            prefs.getBackfillLookbackHours(),
            prefs.getBackfillMaxRows(),
        )
        binding.versionText.text = getString(
            R.string.settings_version_subtitle,
            BuildConfig.VERSION_NAME,
            BuildConfig.VERSION_CODE,
        )
    }

    private fun host(): MainActivity? = activity as? MainActivity

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
