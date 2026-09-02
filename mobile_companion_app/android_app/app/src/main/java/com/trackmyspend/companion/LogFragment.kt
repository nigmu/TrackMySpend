package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.trackmyspend.companion.databinding.FragmentLogBinding
import com.trackmyspend.companion.databinding.ItemLogBinding

class LogFragment : Fragment() {

    private var _binding: FragmentLogBinding? = null
    private val binding get() = _binding!!

    private lateinit var prefs: PrefsStore
    private lateinit var adapter: LogAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentLogBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        adapter = LogAdapter()
        binding.recyclerView.layoutManager = LinearLayoutManager(requireContext())
        binding.recyclerView.adapter = adapter
        refreshList()
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    private fun refreshList() {
        val entries = prefs.getUploadLog()
        adapter.submit(entries)
        binding.emptyView.visibility = if (entries.isEmpty()) View.VISIBLE else View.GONE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private class LogAdapter : androidx.recyclerview.widget.RecyclerView.Adapter<LogAdapter.ViewHolder>() {

        private var items: List<UploadLogEntry> = emptyList()

        fun submit(entries: List<UploadLogEntry>) {
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

            fun bind(entry: UploadLogEntry) {
                itemBinding.timestampText.text = entry.timestamp
                itemBinding.senderText.text = entry.sender
                itemBinding.statusText.text = if (entry.success) {
                    "Success: ${entry.message}"
                } else {
                    "Failed: ${entry.message}"
                }
                val color = if (entry.success) R.color.log_success else R.color.log_failure
                itemBinding.statusText.setTextColor(
                    ContextCompat.getColor(itemBinding.root.context, color)
                )
            }
        }
    }
}
