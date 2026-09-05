package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.PopupMenu
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar
import com.trackmyspend.companion.databinding.DialogAddServerBinding
import com.trackmyspend.companion.databinding.FragmentServersBinding
import com.trackmyspend.companion.databinding.ItemServerBinding
import java.util.concurrent.Executors

class ServersFragment : Fragment() {

    private var _binding: FragmentServersBinding? = null
    private val binding get() = _binding!!

    private lateinit var prefs: PrefsStore
    private lateinit var adapter: ServerAdapter
    private val executor = Executors.newSingleThreadExecutor()
    private val health = mutableMapOf<String, HealthStatus>()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentServersBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        adapter = ServerAdapter(
            healthOf = { health[it.id] ?: HealthStatus.UNKNOWN },
            onOverflow = { server, anchor -> showOverflow(server, anchor) },
            onTest = { server -> testServer(server) },
            onUrlClick = { server ->
                Snackbar.make(binding.root, server.url, Snackbar.LENGTH_LONG).show()
            },
        )
        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = adapter
        binding.fabAdd.setOnClickListener { showAddDialog() }
        binding.emptyAddButton.setOnClickListener { showAddDialog() }
        UiChrome.attachSpringPress(binding.fabAdd)
        refreshList()
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    private fun refreshList() {
        val servers = prefs.getServers()
        adapter.submit(servers)
        val atCap = servers.size >= PrefsStore.MAX_SERVERS
        binding.fabAdd.isEnabled = !atCap
        binding.fabAdd.visibility = if (servers.isEmpty()) View.GONE else View.VISIBLE
        binding.emptyView.visibility = if (servers.isEmpty()) View.VISIBLE else View.GONE
        binding.fabAdd.setOnClickListener {
            if (atCap) {
                Snackbar.make(binding.root, R.string.server_limit_reached, Snackbar.LENGTH_LONG).show()
            } else {
                showAddDialog()
            }
        }
    }

    private fun showOverflow(server: ServerConfig, anchor: View) {
        val servers = prefs.getServers()
        val index = servers.indexOfFirst { it.id == server.id }
        PopupMenu(requireContext(), anchor).apply {
            menu.add(0, 1, 0, R.string.edit_server)
            menu.add(0, 2, 1, R.string.delete)
            if (index > 0) menu.add(0, 3, 2, R.string.move_up)
            if (index in 0 until servers.lastIndex) menu.add(0, 4, 3, R.string.move_down)
            setOnMenuItemClickListener { item ->
                when (item.itemId) {
                    1 -> showEditDialog(server)
                    2 -> confirmDelete(server)
                    3 -> {
                        prefs.moveServer(server.id, -1)
                        refreshList()
                    }
                    4 -> {
                        prefs.moveServer(server.id, 1)
                        refreshList()
                    }
                }
                true
            }
        }.show()
    }

    private fun confirmDelete(server: ServerConfig) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.delete_server_title)
            .setMessage(getString(R.string.delete_server_message, server.name))
            .setPositiveButton(R.string.delete) { _, _ ->
                prefs.deleteServer(server.id)
                health.remove(server.id)
                refreshList()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun showAddDialog() {
        if (prefs.getServers().size >= PrefsStore.MAX_SERVERS) {
            Snackbar.make(binding.root, R.string.server_limit_reached, Snackbar.LENGTH_LONG).show()
            return
        }
        showServerSheet(null)
    }

    private fun showEditDialog(server: ServerConfig) {
        showServerSheet(server)
    }

    private fun showServerSheet(existing: ServerConfig?) {
        val dialogBinding = DialogAddServerBinding.inflate(layoutInflater)
        dialogBinding.sheetTitle.setText(if (existing == null) R.string.add_server else R.string.edit_server)
        existing?.let {
            dialogBinding.nameInput.setText(it.name)
            dialogBinding.urlInput.setText(it.url)
            dialogBinding.tokenInput.setText(it.token)
        }
        val dialog = BottomSheetDialog(requireContext(), R.style.ThemeOverlay_TMS_BottomSheet)
        dialog.setContentView(dialogBinding.root)
        dialogBinding.cancelButton.setOnClickListener { dialog.dismiss() }
        dialogBinding.saveButton.setOnClickListener {
            val name = dialogBinding.nameInput.text?.toString().orEmpty()
            val url = dialogBinding.urlInput.text?.toString().orEmpty()
            val token = dialogBinding.tokenInput.text?.toString().orEmpty()
            if (name.isBlank() || url.isBlank()) return@setOnClickListener
            val outboxWasEmpty = MessageStore(requireContext()).isEmpty()
            if (existing == null) {
                prefs.addServer(name, url, token)
            } else {
                prefs.updateServer(existing.id, name, url, token)
            }
            refreshList()
            dialog.dismiss()
            if (outboxWasEmpty) {
                (activity as? MainActivity)?.startBackfill(BackfillSource.AFTER_SERVER_SAVE)
            }
        }
        dialog.show()
    }

    private fun testServer(server: ServerConfig) {
        health[server.id] = HealthStatus.CHECKING
        adapter.notifyDataSetChanged()
        Snackbar.make(binding.root, getString(R.string.server_testing, server.name), Snackbar.LENGTH_SHORT).show()
        executor.execute {
            val (success, message) = SmsUploader.testHealth(server.url)
            binding.root.post {
                health[server.id] = if (success) HealthStatus.OK else HealthStatus.UNREACHABLE
                adapter.notifyDataSetChanged()
                val text = if (success) {
                    getString(R.string.server_test_ok, message)
                } else {
                    getString(R.string.server_test_failed, message)
                }
                Snackbar.make(binding.root, text, Snackbar.LENGTH_LONG).show()
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private class ServerAdapter(
        private val healthOf: (ServerConfig) -> HealthStatus,
        private val onOverflow: (ServerConfig, View) -> Unit,
        private val onTest: (ServerConfig) -> Unit,
        private val onUrlClick: (ServerConfig) -> Unit,
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<ServerAdapter.ViewHolder>() {

        private var items: List<ServerConfig> = emptyList()

        fun submit(servers: List<ServerConfig>) {
            items = servers
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val itemBinding = ItemServerBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            UiChrome.attachSpringPress(itemBinding.testButton)
            return ViewHolder(itemBinding)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position])
        }

        override fun getItemCount(): Int = items.size

        inner class ViewHolder(private val itemBinding: ItemServerBinding) :
            androidx.recyclerview.widget.RecyclerView.ViewHolder(itemBinding.root) {

            fun bind(server: ServerConfig) {
                itemBinding.nameText.text = server.name
                itemBinding.urlText.text = server.url
                itemBinding.priorityText.text = server.priority.toString()
                itemBinding.priorityText.contentDescription = "Priority ${server.priority}"
                StatusPills.applyHealth(itemBinding.statusChip, healthOf(server))
                itemBinding.testButton.setOnClickListener { onTest(server) }
                itemBinding.overflowButton.setOnClickListener { onOverflow(server, it) }
                itemBinding.urlText.setOnClickListener { onUrlClick(server) }
            }
        }
    }
}
