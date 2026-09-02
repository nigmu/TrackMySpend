package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
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

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentServersBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        adapter = ServerAdapter(
            onSetActive = { server ->
                prefs.setActiveServer(server.id)
                refreshList()
            },
            onEdit = { server -> showEditDialog(server) },
            onDelete = { server ->
                prefs.deleteServer(server.id)
                refreshList()
            },
            onTest = { server -> testServer(server) },
        )
        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = adapter
        binding.fabAdd.setOnClickListener { showAddDialog() }
        refreshList()
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    private fun refreshList() {
        val servers = prefs.getServers()
        adapter.submit(servers)
        binding.emptyView.visibility = if (servers.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun showAddDialog() {
        showServerDialog(null)
    }

    private fun showEditDialog(server: ServerConfig) {
        showServerDialog(server)
    }

    private fun showServerDialog(existing: ServerConfig?) {
        val dialogBinding = DialogAddServerBinding.inflate(layoutInflater)
        existing?.let {
            dialogBinding.nameInput.setText(it.name)
            dialogBinding.urlInput.setText(it.url)
        }
        val title = if (existing == null) R.string.add_server else R.string.edit_server
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(title)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.save) { _, _ ->
                val name = dialogBinding.nameInput.text?.toString().orEmpty()
                val url = dialogBinding.urlInput.text?.toString().orEmpty()
                if (name.isBlank() || url.isBlank()) return@setPositiveButton
                if (existing == null) {
                    prefs.addServer(name, url)
                } else {
                    prefs.updateServer(existing.id, name, url)
                }
                refreshList()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun testServer(server: ServerConfig) {
        Snackbar.make(binding.root, "Testing ${server.name}...", Snackbar.LENGTH_SHORT).show()
        executor.execute {
            val (success, message) = SmsUploader.testHealth(server.url)
            binding.root.post {
                val text = if (success) "OK: $message" else "Failed: $message"
                Snackbar.make(binding.root, text, Snackbar.LENGTH_LONG).show()
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private class ServerAdapter(
        private val onSetActive: (ServerConfig) -> Unit,
        private val onEdit: (ServerConfig) -> Unit,
        private val onDelete: (ServerConfig) -> Unit,
        private val onTest: (ServerConfig) -> Unit,
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<ServerAdapter.ViewHolder>() {

        private var items: List<ServerConfig> = emptyList()

        fun submit(servers: List<ServerConfig>) {
            items = servers
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val itemBinding = ItemServerBinding.inflate(LayoutInflater.from(parent.context), parent, false)
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
                itemBinding.activeRadio.isChecked = server.active
                itemBinding.activeRadio.setOnClickListener { onSetActive(server) }
                itemBinding.testButton.setOnClickListener { onTest(server) }
                itemBinding.editButton.setOnClickListener { onEdit(server) }
                itemBinding.deleteButton.setOnClickListener { onDelete(server) }
            }
        }
    }
}
