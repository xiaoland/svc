import Foundation

struct ProjectSection: Codable, Identifiable {
    let id: UUID
    var name: String
    var collapsed = false
}

struct ProjectOrganization: Codable {
    var schemaVersion = 1
    var sections: [ProjectSection] = []
    var assignments: [String: UUID] = [:]

    var isValid: Bool {
        let ids = Set(sections.map(\.id))
        let names = sections.map { $0.name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
        return schemaVersion == 1 && ids.count == sections.count
            && names.allSatisfy { !$0.isEmpty } && Set(names).count == names.count
            && assignments.values.allSatisfy { ids.contains($0) }
    }
}

struct ProjectReveal: Equatable {
    let id = UUID()
    let path: String
}
