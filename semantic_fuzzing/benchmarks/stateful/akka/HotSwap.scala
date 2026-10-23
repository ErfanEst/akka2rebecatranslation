package stateful.hotSwap
import akka.actor._

case object Foo
case object Bar
case object AlreadyAngry
case object AlreadyHappy
final class HotSwapActor extends Actor {
  def angry: Receive = {
    case Foo => sender() ! AlreadyAngry
    case Bar => context.become(happy)
  }
  def happy: Receive = {
    case Bar => sender() ! AlreadyHappy
    case Foo => context.become(angry)
  }
  def receive: Receive = {
    case Foo => context.become(angry)
    case Bar => context.become(happy)
  }
}
final class Client extends Actor {
  private var angryReplies: Int = 0
  private var happyReplies: Int = 0
  def receive: Receive = {
    case AlreadyAngry => angryReplies += 1
    case AlreadyHappy => happyReplies += 1
  }
}
object HotSwap extends App {
  val system = ActorSystem("HotSwap")
  val worker = system.actorOf(Props[HotSwapActor](), "worker")
  val client = system.actorOf(Props[Client](), "client")
}
