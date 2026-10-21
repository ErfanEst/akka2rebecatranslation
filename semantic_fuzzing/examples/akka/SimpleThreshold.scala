package semanticExamples.simpleThreshold

import akka.actor._

final case class Observe(value: Int)
case object Noop

final class Threshold extends Actor {
  private var lastValue: Int = 0
  private var high: Boolean = false

  override def receive: Receive = {
    case Observe(value) =>
      lastValue = value
      if (value >= 10) {
        high = true
      } else {
        high = false
      }
  }
}

final class Client(threshold: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object SimpleThreshold extends App {
  val system = ActorSystem("SimpleThresholdSystem")
  val threshold = system.actorOf(Props[Threshold](), name = "threshold")
  val client = system.actorOf(Props(new Client(threshold)), name = "client")
}
