package stateful.switchRouter
import akka.actor._
case object RouteStateOn
case object RouteStateOff
final case class Data(value: Int)
case object Noop
final class SwitchActor(normalFlow: ActorRef, cleanUp: ActorRef) extends Actor {
  def on: Receive = {
    case RouteStateOn => ()
    case RouteStateOff => context.become(off)
    case data: Data => normalFlow ! data
  }
  def off: Receive = {
    case RouteStateOn => context.become(on)
    case RouteStateOff => ()
    case data: Data => cleanUp ! data
  }
  def receive: Receive = {
    case RouteStateOn => context.become(on)
    case RouteStateOff => ()
    case data: Data => cleanUp ! data
  }
}
final class Sink extends Actor {
  private var count: Int = 0
  private var total: Int = 0
  def receive: Receive = { case Data(value) => count += 1; total += value }
}
final class Client extends Actor { def receive: Receive = { case Noop => () } }
object SwitchRouter extends App {
  val system = ActorSystem("SwitchRouter")
  val normal = system.actorOf(Props[Sink](), "normal")
  val cleanup = system.actorOf(Props[Sink](), "cleanup")
  val worker = system.actorOf(Props(new SwitchActor(normal, cleanup)), "worker")
  val client = system.actorOf(Props[Client](), "client")
}
