import SwiftUI
import Foundation

@main struct ObserveDisclosureTransaction {
    static func main() throws {
        var expanded = false
        var observed: [[String: Bool]] = []
        let original = Binding<Bool>(get: { expanded }, set: { value, transaction in
            expanded = value
            observed.append(["expanded": value, "animationCleared": transaction.animation == nil,
                             "animationsDisabled": transaction.disablesAnimations, "continuousPreserved": transaction.isContinuous])
        })
        var incoming = Transaction(animation: .easeInOut(duration: 0.4))
        incoming.isContinuous = true
        let disclosure = original.immediateDisclosure.transaction(incoming)
        disclosure.wrappedValue = true
        disclosure.wrappedValue = false
        let valid = !expanded && observed.count == 2 && observed.allSatisfy {
            $0["animationCleared"] == true && $0["animationsDisabled"] == true && $0["continuousPreserved"] == true
        }
        let data = try JSONSerialization.data(withJSONObject: ["valid": valid, "writes": observed,
            "scope": "Binding transaction forwarding, not rendered animation"], options: [.prettyPrinted, .sortedKeys])
        print(String(decoding: data, as: UTF8.self))
        if !valid { exit(1) }
    }
}
