export default function CallToAction() {
  return (
    <section className="bg-[var(--color-primary)] text-white py-12 sm:py-16 md:py-20 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold mb-4 sm:mb-6 leading-tight">
          Ready to Ace Your Next Interview?
        </h2>
        <p className="text-sm sm:text-base md:text-lg lg:text-xl mb-6 sm:mb-8 max-w-2xl mx-auto leading-relaxed">
          Start practicing with AI-powered mock interviews tailored to your dream job.
        </p>
        <div className="flex flex-col sm:flex-row justify-center gap-3 sm:gap-4">
          <a
            href="/signup"
            className="bg-white text-[var(--color-primary)] font-semibold px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg sm:rounded-xl transition-all duration-200 hover:bg-gray-100 shadow-md hover:shadow-lg"
          >
            Get Started Free
          </a>
          <a
            href="/features"
            className="border border-white font-semibold px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg sm:rounded-xl transition-all duration-200 hover:bg-white hover:text-[var(--color-primary)] shadow-md hover:shadow-lg"
          >
            Explore Features
          </a>
        </div>
      </div>
    </section>
  );
}
