export interface TryOnResult {
  id: string;
  personImage: string;
  clothingImage: string;
  resultImage: string;
  clothingName: string;
  createdAt: string;
}

export const mockHistory: TryOnResult[] = [
  {
    id: "1",
    personImage: "/person-1.jpg",
    clothingImage: "/shirt-1.jpg",
    resultImage: "/result-1.jpg",
    clothingName: "Navy Cotton T-Shirt",
    createdAt: "2025-05-28T14:30:00Z",
  },
  {
    id: "2",
    personImage: "/person-2.jpg",
    clothingImage: "/blazer-1.jpg",
    resultImage: "/result-2.jpg",
    clothingName: "Beige Linen Blazer",
    createdAt: "2025-05-27T10:15:00Z",
  },
  {
    id: "3",
    personImage: "/person-1.jpg",
    clothingImage: "/blazer-1.jpg",
    resultImage: "/result-2.jpg",
    clothingName: "Beige Linen Blazer",
    createdAt: "2025-05-25T09:00:00Z",
  },
  {
    id: "4",
    personImage: "/person-2.jpg",
    clothingImage: "/shirt-1.jpg",
    resultImage: "/result-1.jpg",
    clothingName: "Navy Cotton T-Shirt",
    createdAt: "2025-05-20T16:45:00Z",
  },
];

export const features = [
  {
    icon: "Upload",
    title: "Simple Upload",
    description: "Upload your photo and any upper-body clothing image in seconds. Our drag-and-drop interface makes it effortless.",
  },
  {
    icon: "Sparkles",
    title: "AI-Powered Fitting",
    description: "Advanced AI models analyze body shape, fabric texture, and lighting to create photorealistic virtual try-ons.",
  },
  {
    icon: "Zap",
    title: "Instant Results",
    description: "Get your try-on result in under 30 seconds. No waiting, no hassle — just instant fashion visualization.",
  },
  {
    icon: "Download",
    title: "Save & Share",
    description: "Download your generated looks in high resolution or share them directly with friends and on social media.",
  },
  {
    icon: "History",
    title: "Try-On History",
    description: "Access all your past try-ons in one place. Compare outfits and build your personal style archive.",
  },
  {
    icon: "Shield",
    title: "Privacy First",
    description: "Your photos are processed securely and never stored permanently. We delete your images after 24 hours.",
  },
];

export const howItWorks = [
  {
    step: "01",
    title: "Upload Your Photo",
    description: "Take or upload a clear photo of yourself. Make sure your upper body is visible for the best results.",
  },
  {
    step: "02",
    title: "Choose an Outfit",
    description: "Upload any upper-body clothing item — shirts, t-shirts, jackets, blazers, or hoodies from any brand.",
  },
  {
    step: "03",
    title: "AI Magic Happens",
    description: "Our AI analyzes your photo and the clothing item, then generates a realistic try-on in seconds.",
  },
  {
    step: "04",
    title: "View & Download",
    description: "See how the outfit looks on you. Download the result, share it, or try another piece instantly.",
  },
];

export const faqs = [
  {
    question: "What types of clothing work best?",
    answer: "FitCheck AI works best with upper-body clothing like t-shirts, shirts, jackets, blazers, sweaters, and hoodies. The AI focuses on the torso area for the most realistic results. Full-body items like dresses or pants are not supported yet.",
  },
  {
    question: "How long does generation take?",
    answer: "Most try-ons are generated in 20-30 seconds. Processing time may vary slightly depending on image complexity and server load. You'll see a real-time progress indicator while your image is being created.",
  },
  {
    question: "Is my photo kept private?",
    answer: "Absolutely. Your photos are processed securely and automatically deleted from our servers within 24 hours. We never share, sell, or use your images for any purpose other than generating your try-on result.",
  },
  {
    question: "Can I use photos from online stores?",
    answer: "Yes! You can upload clothing images from any online store, brand website, or your own photos. The AI works with product images, flat lays, or photos of clothing on hangers.",
  },
  {
    question: "What photo should I upload of myself?",
    answer: "For best results, use a well-lit photo showing your upper body clearly. Front-facing poses work best. Avoid blurry images, heavy shadows, or photos where your upper body is obscured.",
  },
];
