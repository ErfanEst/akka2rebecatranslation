// Derived benchmark ACSU-04; see ../README_FA.md for changes and upstream licenses.
package validated.calculator
import akka.actor._

final case class Request(one: Int, another: Int)
final case class Sum(one: Int, another: Int)
final case class Multiply(one: Int, another: Int)
final case class RequestMultiply(one: Int, another: Int)
final case class Reply(value: Int)

final class CalculatorActor extends Actor {
  def receive: Receive = {
    case Sum(one, another) => sender() ! Reply(one + another)
    case Multiply(one, another) => sender() ! Reply(one * another)
  }
}
final class Client(calculator: ActorRef) extends Actor {
  private var lastValue: Int = 0
  def receive: Receive = {
    case Request(one, another) => calculator ! Sum(one, another)
    case RequestMultiply(one, another) => calculator ! Multiply(one, another)
    case Reply(value) => lastValue = value
  }
}
object CalculatorBenchmark extends App {
  val system = ActorSystem("CalculatorBenchmark")
  val calculator = system.actorOf(Props[CalculatorActor](), name = "calculator")
  val client = system.actorOf(Props(new Client(calculator)), name = "client")
}
