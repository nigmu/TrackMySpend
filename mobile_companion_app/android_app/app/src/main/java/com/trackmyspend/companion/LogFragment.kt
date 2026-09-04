package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.work.WorkManager
import com.google.android.material.snackbar.Snackbar
import com.trackmyspend.companion.databinding.FragmentLogBinding
import com.trackmyspend.companion.databinding.ItemLogBinding

class LogFragment : Fragment() {

    private var _binding: FragmentLogBinding? = null
    private val binding get() = _binding!!

    private lateinit var store: MessageStore
    private lateinit var adapter: LogAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentLogBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        store = MessageStore(requireContext())
        adapter = LogAdapter { message ->
            if (UploadWorker.retry(requireContext(), message.messageId)) {
                Snackbar.make(binding.root, R.string.retry_queued, Snackbar.LENGTH_SHORT).show()
                refreshList()
            }
        }
        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = adapter
        WorkManager.getInstance(requireContext())
            .getWorkInfosByTagLiveData(UploadWorker.TAG)
            .observe(viewLifecycleOwner) { refreshList() }
        refreshList()
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    private fun refreshList() {
        val entries = store.getAll()
        adapter.submit(entries)
        binding.emptyView.visibility = if (entries.isEmpty()) View.VISIBLE else View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private class LogAdapter(
        private val onRetry: (OutboxMessage) -> Unit,
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<LogAdapter.ViewHolder>() {

        private var items: List<OutboxMessage> = emptyList()

        fun submit(entries: List<OutboxMessage>) {
            items = entries
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val itemBinding = ItemLogBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            return ViewHolder(itemBinding)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position])
        }

        override fun getItemCount(): Int = items.size

        inner class ViewHolder(private val itemBinding: ItemLogBinding) :
            androidx.recyclerview.widget.RecyclerView.ViewHolder(itemBinding.root) {

            fun bind(entry: OutboxMessage) {
                itemBinding.timestampText.text = itemBinding.root.context.getString(
                    R.string.received_at,
                    entry.receivedAt,
                )
                itemBinding.senderText.text = senderSnippet(entry.sender)
                itemBinding.statusText.text = itemBinding.root.context.getString(
                    R.string.delivery_status,
                    entry.status.name.lowercase().replaceFirstChar { it.uppercase() },
                    itemBinding.root.resources.getQuantityString(
                        R.plurals.attempt_count,
                        entry.attemptCount,
                        entry.attemptCount,
                    ),
                )
                val color = when (entry.status) {
                    DeliveryStatus.SENT -> R.color.log_success
                    DeliveryStatus.FAILED -> R.color.log_failure
                    else -> R.color.log_pending
                }
                itemBinding.statusText.setTextColor(
                    ContextCompat.getColor(itemBinding.root.context, color)
                )
                val details = buildString {
                    append("ID ${entry.messageId.take(8)}")
                    entry.ackedAt?.let {
                        append("\n")
                        append(itemBinding.root.context.getString(R.string.acked_at, it))
                    }
                    if (entry.lastServerUrl.isNotBlank()) {
                        append("\n")
                        append(entry.lastServerUrl)
                    }
                    if (entry.httpCode != null) {
                        append(" · ")
                        append("HTTP ${entry.httpCode}")
                    }
                    entry.lastError?.let {
                        append("\n")
                        append(it)
                    }
                }
                itemBinding.detailText.text = details
                itemBinding.retryButton.visibility =
                    if (entry.status == DeliveryStatus.FAILED) View.VISIBLE else View.GONE
                itemBinding.retryButton.setOnClickListener { onRetry(entry) }
            }

            private fun senderSnippet(sender: String): String {
                return if (sender.length <= 24) sender else sender.take(21) + "..."
            }
        }
    }
}
