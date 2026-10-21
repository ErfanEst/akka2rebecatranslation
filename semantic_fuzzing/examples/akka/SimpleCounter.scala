package semanticExamples.simpleCounter

import akka.actor._

final case class Increment(amount: Int)
case object Reset
case object Noop

final class Counter extends Actor {
  private var value: Int = 0
  private var resetSeen: Boolean = false

  override def receive: Receive = {
    case Increment(amount) =>
      value += amount
      resetSeen = false

    case Reset =>
      value = 0
      resetSeen = true
  }
}

final class Client(counter: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object SimpleCounter extends App {
  val system = ActorSystem("SimpleCounterSystem")
  val counter = system.actorOf(Props[Counter](), name = "counter")
  val client = system.actorOf(Props(new Client(counter)), name = "client")
}
