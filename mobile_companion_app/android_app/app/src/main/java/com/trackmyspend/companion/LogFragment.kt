package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
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
    private var filter: LogFilter = LogFilter.ALL

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentLogBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        store = MessageStore(requireContext())
        adapter = LogAdapter { message, button ->
            UiChrome.springScale(button, 0.94f)
            button.postDelayed({ UiChrome.springScale(button, 1f) }, 120)
            if (UploadWorker.retry(requireContext(), message.messageId)) {
                Snackbar.make(binding.root, R.string.retry_queued, Snackbar.LENGTH_SHORT).show()
                refreshList()
            }
        }
        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = adapter
        binding.filterGroup.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            filter = when (checkedId) {
                R.id.filterFailed -> LogFilter.FAILED
                R.id.filterSent -> LogFilter.SENT
                else -> LogFilter.ALL
            }
            refreshList()
        }
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
        val entries = store.getAll().filter { entry ->
            when (filter) {
                LogFilter.ALL -> true
                LogFilter.FAILED -> entry.status == DeliveryStatus.FAILED
                LogFilter.SENT -> entry.status == DeliveryStatus.SENT
            }
        }
        adapter.submit(entries)
        val empty = entries.isEmpty()
        binding.emptyView.visibility = if (empty) View.VISIBLE else View.GONE
        binding.emptyTitle.setText(if (filter == LogFilter.ALL) R.string.no_logs else R.string.no_filtered_logs)
        binding.emptyBody.visibility = if (filter == LogFilter.ALL) View.VISIBLE else View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private enum class LogFilter { ALL, FAILED, SENT }

    private class LogAdapter(
        private val onRetry: (OutboxMessage, View) -> Unit,
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<LogAdapter.ViewHolder>() {

        private var items: List<OutboxMessage> = emptyList()
        private val expanded = mutableSetOf<String>()

        fun submit(entries: List<OutboxMessage>) {
            items = entries
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val itemBinding = ItemLogBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            UiChrome.attachSpringPress(itemBinding.retryButton)
            return ViewHolder(itemBinding)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position])
        }

        override fun getItemCount(): Int = items.size

        inner class ViewHolder(private val itemBinding: ItemLogBinding) :
            androidx.recyclerview.widget.RecyclerView.ViewHolder(itemBinding.root) {

            fun bind(entry: OutboxMessage) {
                val ctx = itemBinding.root.context
                itemBinding.timestampText.text = ctx.getString(R.string.received_at, entry.receivedAt)
                itemBinding.senderText.text = senderSnippet(entry.sender)
                StatusPills.applyDelivery(itemBinding.statusChip, entry.status)
                itemBinding.attemptBadge.text = entry.attemptCount.toString()
                itemBinding.attemptBadge.contentDescription = ctx.resources.getQuantityString(
                    R.plurals.attempt_count,
                    entry.attemptCount,
                    entry.attemptCount,
                )
                itemBinding.messageIdText.text = ctx.getString(R.string.log_message_id, entry.messageId)
                if (entry.ackedAt != null) {
                    itemBinding.ackedText.visibility = View.VISIBLE
                    itemBinding.ackedText.text = ctx.getString(R.string.acked_at, entry.ackedAt)
                } else {
                    itemBinding.ackedText.visibility = View.GONE
                }
                if (entry.lastServerUrl.isNotBlank()) {
                    itemBinding.serverUrlText.visibility = View.VISIBLE
                    itemBinding.serverUrlText.text = entry.lastServerUrl
                } else {
                    itemBinding.serverUrlText.visibility = View.GONE
                }
                if (entry.httpCode != null) {
                    itemBinding.httpCodeText.visibility = View.VISIBLE
                    itemBinding.httpCodeText.text = ctx.getString(R.string.log_http_code, entry.httpCode)
                } else {
                    itemBinding.httpCodeText.visibility = View.GONE
                }
                if (entry.lastError != null) {
                    itemBinding.errorText.visibility = View.VISIBLE
                    itemBinding.errorText.text = entry.lastError
                } else {
                    itemBinding.errorText.visibility = View.GONE
                }
                val isExpanded = entry.messageId in expanded
                itemBinding.detailsGroup.visibility = if (isExpanded) View.VISIBLE else View.GONE
                itemBinding.root.contentDescription =
                    if (isExpanded) ctx.getString(R.string.collapse_details) else ctx.getString(R.string.expand_details)
                itemBinding.root.setOnClickListener {
                    if (isExpanded) expanded.remove(entry.messageId) else expanded.add(entry.messageId)
                    notifyItemChanged(bindingAdapterPosition)
                }
                itemBinding.retryButton.visibility =
                    if (entry.status == DeliveryStatus.FAILED && entry.sender != MessageStore.BACKFILL_SENDER) {
                        View.VISIBLE
                    } else {
                        View.GONE
                    }
                itemBinding.retryButton.setOnClickListener { onRetry(entry, it) }
            }

            private fun senderSnippet(sender: String): String {
                return if (sender.length <= 24) sender else sender.take(21) + "..."
            }
        }
    }
}
