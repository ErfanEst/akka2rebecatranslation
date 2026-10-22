// Derived benchmark ACSU-03; see ../README_FA.md for changes and upstream licenses.
package validated.adder
import akka.actor._

final case class Request(value: Int)
final case class Add(value: Int)
final case class Reply(value: Int)

final class AdderActor(magicNumber: Int) extends Actor {
  def receive: Receive = {
    case Add(value) => sender() ! Reply(value + magicNumber)
  }
}
final class Client(adder: ActorRef) extends Actor {
  private var lastValue: Int = 0
  def receive: Receive = {
    case Request(value) => adder ! Add(value)
    case Reply(value) => lastValue = value
  }
}
object AdderBenchmark extends App {
  val system = ActorSystem("AdderBenchmark")
  val adder = system.actorOf(Props(new AdderActor(4)), name = "adder")
  val client = system.actorOf(Props(new Client(adder)), name = "client")
}
