package stateful.swapper
import akka.actor._

case object Swap
case object Noop
final class SwapperActor extends Actor {
  private var greeting: Int = 0
  def receive: Receive = {
    case Swap =>
      greeting = 1
      context.become(alternate, discardOld = false)
  }
  def alternate: Receive = {
    case Swap =>
      greeting = 2
      context.unbecome()
  }
}
final class Client extends Actor {
  def receive: Receive = { case Noop => () }
}
object Swapper extends App {
  val system = ActorSystem("Swapper")
  val worker = system.actorOf(Props[SwapperActor](), "worker")
  val client = system.actorOf(Props[Client](), "client")
}
