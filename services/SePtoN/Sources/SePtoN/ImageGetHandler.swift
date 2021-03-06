import NIO
import NIOExtras
import Foundation

public final class ImageGetHandler: ChannelInboundHandler {
    public typealias InboundIn = ByteBuffer
    public typealias OutboundOut = ByteBuffer

    let dirSize: UInt32 = 500

    let filesProvider: FilesProvider

    init(_ filesProvider: FilesProvider){
        self.filesProvider = filesProvider
    }

    public func channelRead(context: ChannelHandlerContext, data: NIOAny) {
        var byteBuffer = unwrapInboundIn(data)
        if byteBuffer.readableBytes > MemoryLayout<Int32>.size {
            print("Invalid file id length \(byteBuffer.readableBytes)")
            context.close(promise: nil)
            return
        }

        guard let id: Int32 = byteBuffer.readInteger() else {
            print("Can't read file id from client")
            context.close(promise: nil)
            return
        }

        let path = filesProvider.getFilePathForId(id);

        guard let data = try? Data(contentsOf: path) else {
            print("Can't read file from \(path)")
            context.close(promise: nil)
            return
        }

        var buffer = context.channel.allocator.buffer(capacity: data.count)
        buffer.writeBytes(data)

// Responding with our g^b mod p back to Client
        context.writeAndFlush(self.wrapOutboundOut(buffer), promise: nil)
    }

    public func channelReadComplete(context: ChannelHandlerContext) {
        context.flush()
    }

    public func errorCaught(context: ChannelHandlerContext, error: Error) {
        print("error: ", error)
        context.close(promise: nil)
    }
}