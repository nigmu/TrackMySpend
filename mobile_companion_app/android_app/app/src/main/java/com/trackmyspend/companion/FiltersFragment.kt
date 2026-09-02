package com.trackmyspend.companion

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.trackmyspend.companion.databinding.DialogAddFilterBinding
import com.trackmyspend.companion.databinding.FragmentFiltersBinding
import com.trackmyspend.companion.databinding.ItemFilterBinding

class FiltersFragment : Fragment() {

    private var _binding: FragmentFiltersBinding? = null
    private val binding get() = _binding!!

    private lateinit var prefs: PrefsStore
    private lateinit var adapter: FilterAdapter

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentFiltersBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        prefs = PrefsStore(requireContext())
        adapter = FilterAdapter(
            onDelete = { filter ->
                prefs.deleteFilter(filter.id)
                refreshList()
            }
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
        val filters = prefs.getFilters()
        adapter.submit(filters)
        binding.emptyView.visibility = if (filters.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun showAddDialog() {
        val dialogBinding = DialogAddFilterBinding.inflate(layoutInflater)
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.add_filter)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.save) { _, _ ->
                val pattern = dialogBinding.patternInput.text?.toString().orEmpty()
                if (pattern.isBlank()) return@setPositiveButton
                prefs.addFilter(pattern)
                refreshList()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private class FilterAdapter(
        private val onDelete: (SenderFilter) -> Unit,
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<FilterAdapter.ViewHolder>() {

        private var items: List<SenderFilter> = emptyList()

        fun submit(filters: List<SenderFilter>) {
            items = filters
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val itemBinding = ItemFilterBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            return ViewHolder(itemBinding)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position])
        }

        override fun getItemCount(): Int = items.size

        inner class ViewHolder(private val itemBinding: ItemFilterBinding) :
            androidx.recyclerview.widget.RecyclerView.ViewHolder(itemBinding.root) {

            fun bind(filter: SenderFilter) {
                itemBinding.patternText.text = filter.pattern
                itemBinding.enabledText.text = if (filter.enabled) "Enabled" else "Disabled"
                itemBinding.deleteButton.setOnClickListener { onDelete(filter) }
            }
        }
    }
}
