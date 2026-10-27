import SwiftUI

struct SectionNameEditor: View {
    let sectionID: UUID?
    let store: AppStore
    let close: () -> Void
    @State private var name: String

    init(sectionID: UUID?, name: String, store: AppStore, close: @escaping () -> Void) {
        self.sectionID = sectionID
        self.store = store
        self.close = close
        _name = State(initialValue: name)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(sectionID == nil ? "新建 Section" : "重命名 Section").font(.headline)
            TextField("Section 名称", text: $name)
                .textFieldStyle(.roundedBorder).accessibilityIdentifier("section-name")
                .onSubmit(save)
            HStack {
                Spacer()
                ResourceActionButton(title: "取消", semanticID: "section-editor/cancel", action: close)
                ResourceActionButton(title: "保存", semanticID: "section-editor/save",
                                     enabled: store.canEditSections && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                                     action: save)
            }
        }.padding(16)
    }

    private func save() {
        let saved = sectionID.map { store.renameSection($0, to: name) }
            ?? (store.createSection(name) != nil)
        if saved { close() }
    }
}
