// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SVCMenuBar",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "SVCMenuBar", targets: ["SVCMenuBar"])],
    targets: [
        .executableTarget(name: "SVCMenuBar"),
        .testTarget(name: "SVCMenuBarTests", dependencies: ["SVCMenuBar"])
    ]
)
