// Derived benchmark ACSU-01; see ../README_FA.md for changes and upstream licenses.
package validated.echo
import akka.actor._

final case class Request(value: Int)
final case class EchoValue(value: Int)
final case class Reply(value: Int)

final class EchoActor extends Actor {
  def receive: Receive = {
    case EchoValue(value) => sender() ! Reply(value)
  }
}
final class Client(echo: ActorRef) extends Actor {
  private var lastValue: Int = 0
  def receive: Receive = {
    case Request(value) => echo ! EchoValue(value)
    case Reply(value) => lastValue = value
  }
}
object EchoBenchmark extends App {
  val system = ActorSystem("EchoBenchmark")
  val echo = system.actorOf(Props[EchoActor](), name = "echo")
  val client = system.actorOf(Props(new Client(echo)), name = "client")
}
