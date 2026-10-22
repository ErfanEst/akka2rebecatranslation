// Derived benchmark ACSU-42; see ../README_FA.md for changes and upstream licenses.
package validated.fibonacci
import akka.actor._

final case class Request(value: Int)
final case class Calculate(value: Int)
final case class Reply(value: Int)

final class FibonacciActor extends Actor {
  def receive: Receive = {
    case Calculate(value) => sender() ! Reply(fib(value))
  }
  def fib(n: Int): Int = n match {
    case 0 | 1 => n
    case _ => fib(n - 1) + fib(n - 2)
  }
}
final class Client(fibonacci: ActorRef) extends Actor {
  private var lastValue: Int = 0
  def receive: Receive = {
    case Request(value) => fibonacci ! Calculate(value)
    case Reply(value) => lastValue = value
  }
}
object FibonacciBenchmark extends App {
  val system = ActorSystem("FibonacciBenchmark")
  val fibonacci = system.actorOf(Props[FibonacciActor](), name = "fibonacci")
  val client = system.actorOf(Props(new Client(fibonacci)), name = "client")
}
