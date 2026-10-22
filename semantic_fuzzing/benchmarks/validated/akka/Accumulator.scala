// Derived benchmark ACSU-05; see ../README_FA.md for changes and upstream licenses.
package validated.accumulator
import akka.actor._

final case class Request(value: Int)
final case class Add(value: Int)

final class SummingActor extends Actor {
  private var sum: Int = 0
  def receive: Receive = {
    case Add(value) => sum = sum + value
  }
}
final class Client(accumulator: ActorRef) extends Actor {
  def receive: Receive = {
    case Request(value) => accumulator ! Add(value)
  }
}
object AccumulatorBenchmark extends App {
  val system = ActorSystem("AccumulatorBenchmark")
  val accumulator = system.actorOf(Props[SummingActor](), name = "accumulator")
  val client = system.actorOf(Props(new Client(accumulator)), name = "client")
}
