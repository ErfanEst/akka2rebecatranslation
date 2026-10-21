package semanticExamples.mediumWallet

import akka.actor._

final case class Credit(amount: Int)
final case class Debit(amount: Int)
case object Noop

final class Wallet extends Actor {
  private var balance: Int = 0
  private var lastDebitSucceeded: Boolean = false

  override def receive: Receive = {
    case Credit(amount) =>
      balance += amount

    case Debit(amount) =>
      if (balance >= amount) {
        balance -= amount
        lastDebitSucceeded = true
      } else {
        lastDebitSucceeded = false
      }
  }
}

final class Client(wallet: ActorRef) extends Actor {
  override def receive: Receive = {
    case Noop => ()
  }
}

object MediumWallet extends App {
  val system = ActorSystem("MediumWalletSystem")
  val wallet = system.actorOf(Props[Wallet](), name = "wallet")
  val client = system.actorOf(Props(new Client(wallet)), name = "client")
}
