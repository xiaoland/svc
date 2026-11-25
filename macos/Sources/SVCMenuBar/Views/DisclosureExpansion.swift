import SwiftUI

extension Binding where Value == Bool {
    var immediateDisclosure: Binding<Bool> {
        Binding(get: { wrappedValue }, set: { value, transaction in
            var immediate = transaction
            immediate.animation = nil
            immediate.disablesAnimations = true
            // The state write must also cover the parent's layout and sibling positions.
            withTransaction(immediate) {
                self.transaction(immediate).wrappedValue = value
            }
        })
    }
}
