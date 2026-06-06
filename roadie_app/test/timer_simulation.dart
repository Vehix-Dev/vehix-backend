import 'dart:async';

void main() async {
  print("=== STARTING TIMER SIMULATION ===");
  print("Simulating the OLD way (timeLeft--) vs NEW way (expiryTime)...");
  
  int oldTimeLeft = 15;
  int newTimeLeft = 15;
  
  // New way uses absolute time
  final DateTime expiryTime = DateTime.now().add(Duration(seconds: 15));
  
  print("\n[Time 0s] Dialog Appears");
  print("OLD Timer shows: ${oldTimeLeft}s");
  print("NEW Timer shows: ${newTimeLeft}s");

  // Let 2 seconds pass normally...
  await Future.delayed(Duration(seconds: 2));
  
  // Timer ticks normally for 2 seconds
  oldTimeLeft -= 2;
  newTimeLeft = expiryTime.difference(DateTime.now()).inSeconds;
  
  print("\n[Time 2s] You look at the modal");
  print("OLD Timer shows: ${oldTimeLeft}s");
  print("NEW Timer shows: ${newTimeLeft}s");
  
  print("\n⏸️ Simulating: App goes to background! OS suspends the app.");
  print("The internal timers stop ticking...");
  
  // Simulating 10 seconds passing in the real world while the app is frozen
  await Future.delayed(Duration(seconds: 10));
  
  print("\n▶️ Simulating: App resumes after 10 seconds!");
  
  // When app resumes, the next timer tick fires.
  // Old way: blind decrement.
  oldTimeLeft--;
  // New way: calculates from expiryTime
  newTimeLeft = expiryTime.difference(DateTime.now()).inSeconds;
  
  print("\n[Time 12s] You open the app again");
  print("OLD Timer (timeLeft--) shows: ${oldTimeLeft}s ❌ (It falsely thinks only 3 seconds passed!)");
  print("NEW Timer (expiryTime) shows: ${newTimeLeft}s ✅ (It knows 12 seconds passed!)");
  
  print("\n=== TEST COMPLETED ===");
}
